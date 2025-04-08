# arXiv-filter

Filters the arXiv submissions and only sends the relevant ones based on a set of keywords

![alt text](https://github.com/MarcSerraPeralta/arXiv-filter/blob/main/example_email.png?raw=true)


## What to set up after forking this repo

The requirements to run the `arXiv-filter` are the following:
- have a Gmail account
- have 2-step verification enabled in this account (see [how to set up 2-step verification](https://support.google.com/accounts/answer/185839?hl=en&co=GENIE.Platform%3DAndroid)) 
- have an App Password for this account (see [create an app password](https://support.google.com/accounts/answer/185833?hl=en))

This steps are required so that Github can send an email on your behalf.

### Add Github (repository) secrets

For Github to securely send an email on your behalf, you need to set up two secrets in this repository.
The secrets allow to store your usename and password securely so that only you and Github know them.

To add a secret, go to the repository: 
Settings > Security > Secrets and variables > Actions > New repository secret

Then create the following secrets:
- `MAIL_USERNAME` containing your email (e.g. `example@gmail.com`)
- `MAIL_PASSWORD` containing the App Password for this account (e.g. `aaaa aaaa aaaa aaaa`)

## Specify `from` and `to` for the emails

Go to the file `arXiv-filter/.github/workflows/automatic_filter.yaml` and edit lines 37 and 38:
```
          to: m.serraperalta@tudelft.nl
          from: Marc Serra Peralta
```
to specify the email where you want to receive the automatic emails (it can be the same Gmail account) in `to` and the name of the sender (i.e. your Gmail account) in `from`. 

Optionally, if you want to be able to manually trigger the arXiv processing and 'automatic' email,
then also edit the `arXiv-filter/.github/workflows/manual_filter.yaml` file.

## Add your keywords

Add/Delete/Change the keywords you want to use for filtering in `filters.yaml`.
You can specify keywords to be searched in the title, summary/abstract, and authors.
