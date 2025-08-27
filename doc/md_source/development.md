# 💻 Development

## Contributing

Have you found a bug in **VeraGrid** or have a suggestion for a new functionality? Then
get in touch with us by opening up an issue on the 
[issue board](https://github.com/SanPen/VeraGrid/issues) 
or [join the community discord chat](https://discord.com/invite/dzxctaNbvu) 
to discuss possible new
developments with the community and the maintainers.

### Setup your git repository

**Note**: *The following setup is just a suggestion of how to setup your repository*
*and is supposed to make contributing easier, especially for newcomers. If you have a*
*different setup that you are more comfortable with, you do not have to adopt this*
*setup.*

If you want to contribute for the first time, you can set up your environment like
this:

- If you have not done it yet: install git and create a GitHub account;
- Create a fork of the official **VeraGrid** repository by clicking on "Fork" in the official repository;
- Clone the forked repository to your local machine: `git clone https://github.com/YOUR-USERNAME/VeraGrid.git`
- Copy the following configuration at the bottom of to the `veragrid/.git/config` file (the .git folder is hidden, 
so you might have to enable showing hidden folders) and insert your github username:

```
[remote "origin"]
    url = https://github.com/YOUR-USERNAME/VeraGrid.git
    fetch = +refs/heads/*:refs/remotes/origin/*
    pushurl = https://github.com/YOUR-USERNAME/VeraGrid.git
[remote "upstream"]
    url = https://github.com/SanPen/VeraGrid.git
    fetch = +refs/heads/*:refs/remotes/upstream/*
[branch "master"]
    remote = origin
    merge = refs/heads/master
```
    

The `master` branch is now configured to automatically track the official **VeraGrid**
master branch. So if you are on the `master` branch and use:

```bash
git fetch upstream
git merge upstream/master
```

...your local repository will be updated with the newest changes in the official
**VeraGrid** repository.

Since you cannot push directly to the official **VeraGrid** repository, if you are on
`master` and do:

```bash
git push
```

...your push is by default routed to your own fork instead of the official **VeraGrid**
repository with the setting as defined above.

### Contribute

All contributions to the **VeraGrid** repository are made through pull requests to the
`devel` branch. You can either submit a pull request from the develop branch of your
fork or create a special feature branch that you keep the changes on. A feature branch
is the way to go if you have multiple issues that you are working on in parallel and
want to submit with separate pull requests. If you only have small, one-time changes
to submit, you can also use the `devel` branch to submit your pull request.

If you wish to discuss a contribution before the pull request is ready to be officially
submitted, create an issue in the official repository and link to your own fork. **Do**
**not create pull requests that are not ready to be merged!**

**Note**: *The following guide assumes the remotes are set up as described above. If*
*you have a different setup, you will have to adapt the commands accordingly.*

### Test Suite

**VeraGrid** uses pytest for automatic software testing.

If you make changes to **VeraGrid** that you plan to submit, first make sure that all
tests are still passing. You can do this locally with:

```bash
pytest
```

If you have added new functionality, you should also add a new function that tests this
functionality. pytest automatically detects all functions in the `src/tests` folder
that start with `test_` and are located in a file that also starts with `test_` as
relevant test cases.

## Testing with pytest

Unit test (for pytest) are included in `src/tests`. As defined in `pytest.ini`, all
files matching `test_*.py` are executed by running:

```bash
pytest
```

Files matching `*_test.py` are not executed; they were not formatted specifically for
`pytest` but were mostly done for manual testing and documentation purposes.

Additional tests should be developed for each new and existing feature. `pytest`
should be run before each commit to prevent easily detectable bugs.