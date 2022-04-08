# edx_replace_staff

Adds and/or removes staff in multiple edX courses at once.

Using this script requires a CSV file with the following headers:

* **URL** - the address of class' Course Team Settings page.
* **Add** - the e-mail addresses of the staff to be added.
* **Promote** - promotes an existing staff member to Admin.
* **Remove** - removes staff from the course, regardless of whether they're currently Admin or not.
* **Demote** - removes Admin status, but leaves the user as staff.

When you have multiple people in any of these categories, space-separate them. You can find an example in the test folder.

This repo includes a Mac version of the [Chrome webdriver](https://chromedriver.chromium.org/), which is licensed under the a [separate set of terms](https://chromium.googlesource.com/chromium/src/+/HEAD/LICENSE). If you need a different version of the driver you'll have to replace that file (using the same name).

Instructions
-------------

To install and use for the first time:

    # clone this repo
    $> git clone https://github.com/Colin-Fredericks/edx_replace_staff.git

    # create a virtualenv and activate it
    $> python3 -m venv edxstaff
    $> source edxstaff/bin/activate
    (edxstaff) $>

    # install requirements
    (edxstaff) $> cd hx_util
    (edxstaff) $> pip3 install -r requirements.txt

    # install hx_util
    (edxstaff) $> pip3 install .

    # to add or remove staff
    (edxstaff) $> edx_replace_staff /path/to/input/csv

    # when done
    (edxstaff) $> deactivate

On later runs you can do a simpler version:

  $> source edxstaff/bin/activate
  (edxstaff) $> edx_replace_staff /path/to/input/csv
  (edxstaff) $> deactivate

Run the whole process from the top if you need to reinstall (for instance, if the script and/or its requirements change).
