import sys
import time
import random
from datetime import datetime, timedelta, timezone
import urllib.request as libreq
import argparse

import yaml


def get_attr(xml_str: str, attr: str) -> str:
    xml_attr = f"<{attr}>"
    if not xml_attr in xml_str:
        raise ValueError(f"Attribute '{attr}' not found in '{xml_str}'.")

    idx1 = xml_str.index(xml_attr) + len(xml_attr)
    idx2 = xml_str.index(f"</{attr}>")
    return xml_str[idx1:idx2]


def get_attr_list(xml_str: str, attr: str) -> list[str]:
    attr_list = []
    xml_attr_1 = f"<{attr}>"
    xml_attr_2 = f"</{attr}>"
    for _ in range(xml_str.count(xml_attr_1)):
        idx1 = xml_str.index(xml_attr_1) + len(xml_attr_1)
        idx2 = xml_str.index(xml_attr_2)
        attr_list.append(xml_str[idx1:idx2])
        xml_str = xml_str[idx2 + len(xml_attr_2) :]
    return attr_list


def highlight_word(text, lower_text, lower_word):
    if lower_word not in lower_text:
        return text

    sentences = lower_text.split(lower_word)
    idx = 0
    new_text = ""
    for sentence in sentences[:-1]:
        new_text += text[idx : idx + len(sentence)]
        idx += len(sentence)
        new_text += f'<span style="background-color: orange;">{text[idx:idx+len(lower_word)]}</span>'
        idx += len(lower_word)
    new_text += text[idx : idx + len(sentences[-1])]
    return new_text


##########################################################
# get the arguments

parser = argparse.ArgumentParser(description="Filter for arxiv submissions")
parser.add_argument(
    "-d",
    "--day",
    help="This script will process new submissions up to specified day (YYYY-MM-DD) at 0:00",
    type=str,
    default=None,
)
parser.add_argument(
    "-c", "--category", help="arXiv category", type=str, default="quant-ph"
)
parser.add_argument(
    "--max-results",
    help="Maximum number of submissions to get from arXiv",
    type=int,
    default=10_000,
)
args = vars(parser.parse_args())

##########################################################
# process default inputs
day = args["day"]
max_results = args["max_results"]
category = args["category"]

# job scheduled at 05:00 UTC (today).
# Arxiv send the email at 0:00 UTC today with the results from:
# 18:00 UTC two days ago - 18:00 UTC yesterday.
day_datetime = datetime.now(timezone.utc).date()
if day is not None:
    day_datetime = datetime.strptime(day, "%Y-%m-%d")
print("input day:", day_datetime.strftime("%Y-%m-%d"))  # debugging

# cancel job if it is saturday or sunday
if day_datetime.weekday() in [5, 6]:
    sys.exit(0)

# get the window of days to extract the submissions.
# if the day is monday, it should load submissions from friday, saturday and sunday
day_window = 1
if day_datetime.weekday() == 0:
    day_window = 3

if max_results > 10_000:
    raise ValueError(
        f"arXiv only allows a maximum number of results <=10000, but {max_results} was given."
    )

##########################################################
# format of the querry
query_format = "http://export.arxiv.org/api/query?search_query=cat:{category}+AND+submittedDate:[{day_0}+TO+{day_1}]&max_results={max_results}"

# prepare '18:00 UTC two days ago' and '18:00 UTC yesterday' dates for arxiv format: YYYYMMDDTTTT
day_1 = (day_datetime - timedelta(days=1)).strftime("%Y%m%d") + "1800"
day_0 = (day_datetime - timedelta(days=1 + day_window)).strftime("%Y%m%d") + "1800"

# run query
query = query_format.format(
    category=category, day_0=day_0, day_1=day_1, max_results=max_results
)
print("query:", query)  # debugging

# avoid error 'ConnectionResetError: [Errno 104] Connection reset by peer'
success = False
num_attempts, max_num_attempts = 0, 100
while (not success) or (num_attempts > max_num_attempts):
    try:
        with libreq.urlopen(query) as url:
            data = url.read()
        success = True
    except:
        # wait between 1 and 2 seconds, do it randomly to avoid detection
        # of data scrapping
        time.sleep(1 + random.random())
        num_attempts += 1

# if data scrapping not successful, send email about it
if not success:
    with open("email.html", "r") as file:
        template_email = file.read()
    formatted_email = template_email.format(
        body="An error occurred in the GitHub action", day_1=day_1, day_0=day_0
    )
    with open("formatted_email.html", "w") as file:
        file.write(formatted_email)
    sys.exit()

# the output of the url is in byte format, not string format
data = data.decode("utf-8")

##########################################################
# process XML data

data = data.split("<entry>")
data_format, data = data[0], data[1:]

# ensure that the format is the expected one
assert (
    '<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
    in data_format
)

data_dict = {}
for element in data:
    link = get_attr(element, "id")
    date = get_attr(element, "published")
    title = get_attr(element, "title")
    summary = get_attr(element, "summary")
    authors = ", ".join(get_attr(x, "name") for x in get_attr_list(element, "author"))
    data_dict[link] = dict(date=date, title=title, summary=summary, authors=authors)


##########################################################
# run filters

with open("filters.yaml", "r") as file:
    filters = yaml.safe_load(file)

# check filters
assert set(filters) <= set(["title", "summary", "authors"])
assert all(isinstance(w, list) for w in filters.values())
for keywords in filters.values():
    for k, keyword in enumerate(keywords):
        # check that there are no overlapping keywords because they will not alter
        # the arxiv submissions that one wants but they will create an incorrect
        # HTML format, .e.g. <span...>q<span...>ldpc</span></span> if qldpc and ldpc
        # are both keywords
        assert keyword not in "".join(keywords[:k] + keywords[k + 1 :])

filtered_data_dict = {}
for link, attributes in data_dict.items():
    for attr_name, keywords in filters.items():
        for keyword in keywords:
            # case unsensitive keywords
            if keyword.lower() in attributes[attr_name].lower():
                filtered_data_dict[link] = attributes
                continue

##########################################################
# create the email

# need to use HTML because plain text does not allow to highlight words
formatted_data = {}
for link, attrs in filtered_data_dict.items():
    formatted_data[link] = attrs
    for attr_name, keywords in filters.items():
        for keyword in keywords:
            text = formatted_data[link][attr_name]
            formatted_data[link][attr_name] = highlight_word(
                text, text.lower(), keyword.lower()
            )

    # remove newlines in title
    formatted_data[link]["title"] = formatted_data[link]["title"].replace("\n", "")

    # format date
    formatted_data[link]["date"] = (
        formatted_data[link]["date"].replace("T", " ").replace("Z", "")
    )

# load template for email and for each arxiv entry
with open("email.html", "r") as file:
    template_email = file.read()
with open("email_arxiv-element.html", "r") as file:
    template_entry = file.read()

formatted_entries = []
for link, attrs in formatted_data.items():
    formatted_entry = template_entry.format(
        formatted_title=attrs["title"],
        formatted_authors=attrs["authors"],
        formatted_summary=attrs["summary"],
        formatted_date=attrs["date"],
        link=link,
        id=link,
    )
    formatted_entries.append(formatted_entry)

if len(formatted_entries) == 0:
    # no arXiv submissions matching the filters
    formatted_entries = ["<p>No submissions matching the filters have been found.</p>"]

formatted_entries = "\n".join(formatted_entries)
formatted_email = template_email.format(
    body=formatted_entries, day_1=day_1, day_0=day_0
)

with open("formatted_email.html", "w") as file:
    file.write(formatted_email)
