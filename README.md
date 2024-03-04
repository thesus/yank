# yank

Yank is meant to export all discussion threads from a [Discourse](https://www.discourse.org/) instance and import them into [Mailman Hyperkitty](https://docs.mailman3.org/projects/hyperkitty/en/latest/). This repository should only be used as starting point. It's just a script cobbled together for one specific use case.

## Getting started

Install the requirements and generate an `mbox` file.
```bash
pip install -r requirements.txt

API_KEY=your_key API_BASE=https://your_discourse.com LIST_NAME=listname@mailman-instance.com python export.py
```

Import into hyperkitty. For more information see [here](https://docs.mailman3.org/projects/hyperkitty/en/latest/install.html#importing-the-current-archives).

```bash
python manage.py hyperkitty_import -l $LIST_NAME export.mbox
```
