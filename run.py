import sys
import urllib.request as libreq

import yaml


def get_title(html_str: str) -> str:
    prefix = '<h1 class="title mathjax"><span class="descriptor">Title:</span>'
    start_idx = html_str.index(prefix) + len(prefix)
    end_idx = html_str[start_idx:].index("</h1>") + start_idx
    return html_str[start_idx:end_idx]


def get_summary(html_str: str) -> str:
    prefix = '<span class="descriptor">Abstract:</span>'
    start_idx = html_str.index(prefix) + len(prefix)
    end_idx = html_str[start_idx:].index("</blockquote>") + start_idx
    return html_str[start_idx:end_idx]


def get_authors(html_str: str) -> list[str]:
    prefix = '<div class="authors"><span class="descriptor">Authors:</span>'
    start_idx = html_str.index(prefix) + len(prefix)
    end_idx = html_str[start_idx:].index("</div>") + start_idx
    authors_block = html_str[start_idx:end_idx]

    authors = []
    while "<a href=" in authors_block:
        prefix = 'rel="nofollow">'
        start_idx = authors_block.index(prefix) + len(prefix)
        end_idx = authors_block[start_idx:].index("</a>") + start_idx
        authors.append(authors_block[start_idx:end_idx])

        # remove author
        authors_block = authors_block[end_idx:]

    return authors


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
# inputs
category = "quant-ph"

##########################################################
# process default inputs

# using arXiv's "new submissions" website for more consistent results than its API.
# With the API, some entries from yesterday were not given, even though they felt
# inside the search parameters specified.

# job scheduled at 05:00 UTC (today).
# Arxiv send the email at 0:00 UTC today with the results from:
# 18:00 UTC two days ago - 18:00 UTC yesterday.

query_template = "https://arxiv.org/list/quant-ph/new?skip={skip}&show={show}"

# get today's number of submissions
query = query_template.format(skip=0, show=2000)
with libreq.urlopen(query) as url:
    data = url.read()
data = data.decode("utf8")

# get today's date
string = "<h3>Showing new listings for "
start_index = data.find(string) + len(string)
end_index = data[start_index:].find("</h3>\n") + start_index
date = data[start_index:end_index]
print("Date:", date)

if date == "":
    with open("email.html", "r") as file:
        template_email = file.read()
    formatted_email = template_email.format(
        body="Bad formatted arXiv data, please check the GitHub Actions",
        date=date,
    )
    with open("formatted_email.html", "w") as file:
        file.write(formatted_email)

    print(data)  # for debugging
    sys.exit()

# check if there are entries today
if "<p>No updates today.</p>" in data:
    with open("email.html", "r") as file:
        template_email = file.read()
    formatted_email = template_email.format(
        body="No submissions matching the filters have been found.",
        date=date,
    )
    with open("formatted_email.html", "w") as file:
        file.write(formatted_email)
    sys.exit()

# check number of entries
num_submissions = None
for line in data.split("\n"):
    if "<h3>New submissions (showing " in line:
        num_submissions = int(line.lstrip().rstrip().split(" ")[-2])
        break

print("Number of submissions:", num_submissions)

if num_submissions is None:
    with open("email.html", "r") as file:
        template_email = file.read()
    formatted_email = template_email.format(
        body="Bad formatted arXiv data, please check the GitHub Actions",
        date=date,
    )
    with open("formatted_email.html", "w") as file:
        file.write(formatted_email)

    print(data)  # for debugging
    sys.exit()

# get arXiv subsmissions
arxiv_entries = []
for k in range(num_submissions // 2000 + 1):
    query = query_template.format(skip=2000 * k, show=2000)
    with libreq.urlopen(query) as url:
        data = url.read()
    data = data.decode("utf8")

    prefix = '<a href ="/abs/'

    for line in data.split("\n"):
        if "<h3>Cross submissions (showing" in line:
            break
        if "<h3>Replacement submissions (showing" in line:
            break
        if (prefix in line) and (' title="Abstract" id=' in line):
            # arXiv entry
            line = line.rstrip().lstrip()
            start_index = len(prefix)
            end_index = line.index('" title=')
            arxiv_entries.append(line[start_index:end_index])

print("Arxiv entries:", arxiv_entries)  # debugging

# get data for each arXiv submission
data_dict = {}
for entry in arxiv_entries:
    link = "https://arxiv.org/abs/" + entry
    with libreq.urlopen(link) as url:
        data = url.read()
    data = data.decode("utf8")

    title = get_title(data)
    summary = get_summary(data)
    authors = ", ".join(get_authors(data))
    data_dict[link] = dict(title=title, summary=summary, authors=authors)

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
        link=link,
        id=link,
    )
    formatted_entries.append(formatted_entry)

if len(formatted_entries) == 0:
    # no arXiv submissions matching the filters
    formatted_entries = ["<p>No submissions matching the filters have been found.</p>"]

formatted_entries = "\n".join(formatted_entries)
formatted_email = template_email.format(
    body=formatted_entries,
    date=date,
)

with open("formatted_email.html", "w") as file:
    file.write(formatted_email)

print("Formatted email:\n", formatted_email)  # for debugging
