import sys
from datetime import datetime, timedelta
import urllib.request as libreq


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
# process default inputs.

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
    title = get_attr(element, "title")
    summary = get_attr(element, "summary")
    authors = [get_attr(x, "name") for x in get_attr_list(element, "author")]
    data_dict[link] = dict(title=title, summary=summary, authors=authors)


##########################################################
# run filters
