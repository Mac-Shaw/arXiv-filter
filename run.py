import sys
from datetime import datetime, timedelta
import urllib.request as libreq

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


# TODO: argparse

# load arguments (use argparse)
day = "2025-03-07"  # None
category = "quant-ph"
max_results = 10_000  # max results to be sent by arxiv

##########################################################
# process default inputs

# job scheduled at 00:05, so we want the results from
# yesterday at 00:00 and today at 00:00.
day_datetime = datetime.today()
if day is not None:
    day_datetime = datetime.strptime(day, "%Y-%m-%d")

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
query_format = "http://export.arxiv.org/api/query?search_query=cat:{category}+AND+submittedDate:[{yesterday}+TO+{today}]&max_results={max_results}"

# prepare today and yesterday dates at midnigh for arxiv format: YYYYMMDDTTTT
today = day_datetime.strftime("%Y%m%d") + "0000"
yesterday = (day_datetime - timedelta(days=day_window)).strftime("%Y%m%d") + "0000"

# run query
query = query_format.format(
    category=category, yesterday=yesterday, today=today, max_results=max_results
)
with libreq.urlopen(query) as url:
    data = url.read()

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
    data_dict[link] = dict(date=data, title=title, summary=summary, authors=authors)


##########################################################
# run filters

with open("filters.yaml", "r") as file:
    filters = yaml.safe_load(file)

assert set(filters) <= set(["title", "summary", "authors"])
assert all(isinstance(w, list) for w in filters.values())

filtered_data_dict = {}
for link, attributes in data_dict.items():
    for attr_name, keywords in filters.items():
        # case unsensitive keywords
        text = attributes[attr_name].lower()
        for keyword in keywords:
            if keyword.lower() in text:
                filtered_data_dict[link] = attributes
                continue

##########################################################
# create the email


# need to use HTML because plain text does not allow for highlighting words
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


formatted_data = {}
for link, attributes in filtered_data_dict.items():
    formatted_data[link] = attributes
    for attr_name, keywords in filters.items():
        for keyword in keywords:
            text = formatted_data[link][attr_name]
            formatted_data[link][attr_name] = highlight_word(
                text, text.lower(), keyword.lower()
            )
    # remove newlines in title
    formatted_data[link]["title"] = formatted_data[link]["title"].replace("\n", "")


print([i["title"] for i in formatted_data.values()])
