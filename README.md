

    /scratch/claude/sessions/9e22f9f3-9b13-4be0-b8b4-0cf604d65390/.cache/toxworkdir_base/code/fbmessengerexport/.tox/quarto/lib/python3.14/site-packages/aenum/__init__.py:220: SyntaxWarning: "\w" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\w"? A raw string is also an option.
      pattern = '^_%s__\w+[^_]_?$' % (cls_name, )

**Warning**: the library this script is using to talk to Facebook API (fbchat) is unmaintained at the moment, so you might experience problems with logging in (or be unable to). See <https://github.com/fbchat-dev/fbchat/issues/638> and other issues for more info.

Export your personal Facebook chat/Messenger data into an sqlite database.

Main difference from “Download your information” export is that this tool can be run automatically and doesn’t require remembering to go onto Facebook website, reentering password, downloading archive, etc.

Note that at the moment it exports **text only**, images or videos are not exported.
I recommend checking the database after initial export to make sure it contains everything you want from the tool!
I cleaned up some things I assumed weren’t useful from raw responses, but I could be misinterpreting something as I’m not a heavy Facebook user.
Feel free to open a github issue if you think something about storage should be changed.

<!-- Keep this separator: Quarto otherwise moves the generated preamble below the following heading. -->

# Setting up

1.  The easiest way is `pip3 install --user git+https://github.com/karlicoss/fbmessengerexport`.

    Alternatively, clone the repository and run `pip3 install --editable .`.

2.  Login and get cookies: `python3 -m fbmessengerexport.export --login --cookies ANYSTRING`

    Note: on this step you need to pass an arbitrary string as `--cookies` parameter, just to make the argument parser happy.
    After login use either the real cookie you got, or the `--secrets` parameter (more on that below).

    Facebook doesn’t have an API, so you’ll have to use cookies.

    Ideally this step needs to be done once, after that just use cookies to access your data.

    Note that this step might prompt you for two factor auth.

    Also Facebook will likely **notify you about unusual login**, so make sure to approve it in
    [security settings](https://www.facebook.com/settings?tab=security).

# Exporting

Usage:

**Recommended**: create `secrets.py` keeping your API parameters, e.g.:

    cookies = "COOKIES"

After that, use:

    python3 -m fbmessengerexport.export --secrets /path/to/secrets.py --db /path/to/export.sqlite

That way you type less and have control over where you keep your plaintext secrets.

**Alternatively**, you can pass parameters directly, e.g.

    python3 -m fbmessengerexport.export --cookies <cookies> --db /path/to/export.sqlite

However, this is verbose and prone to leaking your keys/tokens/passwords in shell history.

I **highly** recommend checking exported files at least once just to make sure they contain everything you expect from your export.
If they don’t, please feel free to ask or raise an issue!

# Using data

You can use this DAL (Data Access/Abstraction Layer) module to access your exported data, even offline.
I elaborate on motivation behind it [here](https://beepb00p.xyz/exports.html#dal).

- the main use case is importing it as a Python module for **programmatic access** to your data.

  You can find some inspiration in [`my.`](https://beepb00p.xyz/mypkg.html) package that I’m using as an API to all my personal data.

- to test it against your export, simply run: `python3 -m fbmessengerexport.dal /path/to/export`

- you can also try it interactively in an IPython shell: `python3 -m fbmessengerexport.dal /path/to/export --interactive`

# Updating README

This README is generated from a ‘literate’ Quarto [README.qmd](README.qmd) via the following command:

`tox -e quarto`

If you want to correct something, feel free to simply update `README.md` though, I can reconcile the changes next time I regenerate it.
