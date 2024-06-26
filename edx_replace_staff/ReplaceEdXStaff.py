#!/usr/bin/env python3
# VPAL Multi-course Staffing Script

import os
import csv
import sys
import time
import logging
import datetime
import argparse
import traceback
from getpass import getpass
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common import exceptions as selenium_exceptions
from selenium.webdriver.support import expected_conditions as EC

# TODO: Better tracking of what we had to skip.

instructions = """
to run:
python3 ReplaceEdXStaff.py filename.csv

The csv file must have these headers/columns:
Course - course name or identifier (optional)
URL - the address of class' Course Team Settings page
Add - the e-mail addresses of the staff to be added. (not usernames)
      If there are multiple staff, space-separate them.
Promote - promote these people to Admin status
Remove - just like "Add"
Demote - removes Admin status

The output is another CSV file that shows which courses couldn't be accessed
and which people couldn't be removed. If the --list option is used,
the CSV instead shows who's admin and staff in all courses.

Options:
  -h or --help:    Print this message and exit.
  -l or --list:    List all staff and admin in all courses. Make no changes.
                   Only requires the URL column.
  -c or --chrome:   Use Chrome instead of default Firefox.
  -v or --visible:  Run the browser in normal mode instead of headless.

"""

# Prep the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler("edx_staffing.log")
formatter = logging.Formatter(
    "%(asctime)s : %(name)s  : %(funcName)s : %(levelname)s : %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


# Just a faster thing to type and read.
def log(text, level="INFO"):
    print(text)
    if level == "DEBUG":
        logger.debug(text)
    if level == "INFO":
        logger.info(text)
    if level == "WARNING":
        logger.warning(text)
    if level == "ERROR":
        logger.error(text)
    if level == "CRITICAL":
        logger.critical(text)


def trimLog(log_file="edx_staffing.log", max_lines=20000):
    """
    Trims a log file to a maximum number of lines.

    Parameters:
    log_file (str): The file to trim.
    max_lines (int): The maximum number of lines to keep.

    Returns:
    void

    """

    with open(log_file, "r") as f:
        lines = f.readlines()
    with open(log_file, "w") as f:
        f.writelines(lines[-max_lines:])


# Instantiating a headless Chrome or Firefox browser
def setUpWebdriver(run_headless, driver_choice):
    log("Setting up webdriver.")
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + os.path.dirname(__file__)

    if driver_choice == "chrome":
        op = ChromeOptions()
        op.add_argument("start-maximized")
        if run_headless:
            op.add_argument("--headless")
        driver = webdriver.Chrome(options=op)
    else:
        op = FirefoxOptions()
        op.binary_location = '/Applications/Firefox.app/Contents/MacOS/firefox'
        if run_headless:
            op.headless = True
        # driver = webdriver.Firefox(options=op)
        driver = webdriver.Firefox(executable_path='/Users/colinfredericks/Documents/GitHub/edx_replace_staff/edx_replace_staff/geckodriver', options=op)

    driver.implicitly_wait(1)
    return driver


def userIsPresent(driver, email):
    is_admin_xpath = "//a[text()='" + email + "']"
    user_present = driver.find_elements(By.XPATH, is_admin_xpath)
    if len(user_present) > 0:
        return True
    else:
        return False


def userIsStaff(driver, email):
    staff_user_css = "li[data-email='" + email.lower() + "'] span.flag-role-staff"
    staff_flag = driver.find_elements(By.CSS_SELECTOR, staff_user_css)
    if len(staff_flag) > 0:
        return True
    else:
        return False


def userIsAdmin(driver, email):

    # Structure:
    # <span class="badge-current-user bg-primary-700 text-light-100 badge badge-primary">
    #   Admin
    #   <span class="badge-current-user x-small text-light-500">
    #     You!
    #   </span>
    # </span>

    # Xpath to find the admin flag for this user.
    is_admin_xpath = (
        "//span[contains(@class, 'badge-current-user')]"
        + "[contains(text(), 'Admin')]"
        + "//span[contains(@class, 'badge-current-user')]"
        + "[contains(text(), 'You!')]"
    )

    admin_flag = driver.find_elements(By.XPATH, is_admin_xpath)
    if len(admin_flag) > 0:
        return True
    else:
        return False


def getAllUsers(driver):
    staff_list = []
    admin_list = []

    staff_xpath = "//span[contains(@class, 'flag-role-staff')]/ancestor::li"
    admin_xpath = "//span[contains(@class, 'flag-role-instructor')]/ancestor::li"

    all_staff = driver.find_elements(By.XPATH, staff_xpath)
    for x in all_staff:
        staff_list.append(x.get_attribute("data-email"))
    all_admins = driver.find_elements(By.XPATH, admin_xpath)
    for y in all_admins:
        admin_list.append(y.get_attribute("data-email"))

    return {"staff": staff_list, "admin": admin_list}


# Returns info about the dialog.
# If there was none, it's "no_dialog"
# If we closed it and they weren't a user, it's "no_user"
# If we couldn't close the dialog, it's "failed_to_close"
def closeErrorDialog(driver):

    # Try to find the "ok" button for the error dialogs.
    wrong_email_css = "#prompt-error.is-shown button.action-primary"
    wrong_email_ok_button = driver.find_elements(By.CSS_SELECTOR, wrong_email_css)

    # If there is an error dialog open, report why, clear it, and move on.
    if len(wrong_email_ok_button) > 0:
        log("error dialog open")
        try:
            # No user with specified e-mail address.
            wrong_email_ok_button[0].click()
            return {"reason": "no_user"}
        except Exception as e:
            # Couldn't close the error dialog.
            # log(repr(e), "DEBUG")
            log("Could not close error dialog for " + driver.title, "WARNING")
            return {"reason": "failed_to_close"}
    # If there's no error dialog, we were successful. Move on.
    else:
        # No error dialog
        return {"reason": "no_dialog"}


def signIn(driver, username, password):
    # Locations
    login_page = "https://authn.edx.org/login"
    username_input_css = "#emailOrUsername"
    password_input_css = "#password"
    login_button_css = "#sign-in"

    # Open the edX sign-in page
    log("Logging in...")
    driver.get(login_page)

    # Wait a second.
    time.sleep(1)

    # Apparently we have to run this more than once sometimes.
    login_count = 0
    while login_count < 3:
        # Sign in
        try:
            found_username_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, username_input_css))
            )
        except selenium_exceptions.TimeoutException:
            driver.quit()
            sys.exit("Timed out waiting for username field.")

        # Wait a second.
        time.sleep(1)

        username_field = driver.find_elements(By.CSS_SELECTOR, username_input_css)[0]
        username_field.clear()
        username_field.send_keys(username)
        log("Username sent")

        # Wait a second.
        time.sleep(1)

        password_field = driver.find_elements(By.CSS_SELECTOR, password_input_css)[0]
        password_field.clear()
        password_field.send_keys(password)
        log("Password sent")

        # Wait a second.
        time.sleep(1)

        # Using ActionChains is necessary because edX put a div over the login button.
        login_button = driver.find_elements(By.CSS_SELECTOR, login_button_css)[0]
        actions = ActionChains(driver)
        actions.move_to_element(login_button).click().perform()
        log("Login button clicked")

        # Check to make sure we're signed in.
        # There are several possible fail states to check for.
        found_dashboard = False
        try:
            log("Finding dashboard...")
            found_dashboard = WebDriverWait(driver, 10).until(EC.url_contains("home"))
        except (
            selenium_exceptions.TimeoutException,
            selenium_exceptions.InvalidSessionIdException,
        ):
            log(traceback.print_exc(), "WARNING")
            login_fail = driver.find_elements(By.CSS_SELECTOR, "#login-failure-alert")
            if len(login_fail) > 0:
                log("Incorrect login or password")
            need_reset = driver.find_elements(
                By.CSS_SELECTOR, "#password-security-reset-password"
            )
            if len(need_reset) > 0:
                log("Password reset required")
            if "Forbidden" in driver.title:
                log("403: Forbidden")

        # If we're logged in, we're done.
        if found_dashboard:
            log("Logged in.")
            return

        login_count += 1
        log("Login attempt count: " + str(login_count))

    driver.close()
    log("Login failed.")
    sys.exit("Login issue or course dashboard page timed out.")


def addStaff(driver, email_list):

    # Locations for add-staff inputs
    new_team_xpath = "//button[text()='New team member']"
    new_staff_email_xpath = "//input[@name='email']"
    add_user_xpath = "//button[text()='Add user']"

    # For each address:
    for email in email_list:
        success = False

        # If the user is already present, move to the next e-mail address.
        if userIsPresent(driver, email):
            log(email + " is already on course team.")
            continue

        # Retry up to 3 times.
        for x in range(0, 3):
            log("Trying to add " + email)

            try:
                # Click the "New Team Member" button
                new_team_buttons = driver.find_elements(By.XPATH, new_team_xpath)
                new_team_buttons[0].click()
            except Exception as e:
                # If that failed, there could be an error message up. Try to close it.
                closeErrorDialog(driver)

            try:
                # Put the e-mail into the input box.
                email_boxes = driver.find_elements(By.XPATH, new_staff_email_xpath)
                email_boxes[0].clear()
                email_boxes[0].send_keys(email)
                # Click "Add User"
                add_user_buttons = driver.find_elements(By.XPATH, add_user_xpath)
                add_user_buttons[0].click()

                # Now that we've clicked the add button,
                # Either the user was added or there's an error dialog.
                if userIsPresent(driver, email):
                    # All good.
                    success = True
                    break
                else:
                    # Clear the dialog and move on to the next e-mail.
                    closeErrorDialog(driver)
                    break

            except Exception as e:
                # If the stuff above failed, it's probably because
                # one of the elements hasn't been added to the page yet.
                log("Couldn't add " + email + ", trying again...")
                # log(repr(e), "DEBUG")

        if success:
            log("Added " + email)
        else:
            log("Could not add " + email)
            closeErrorDialog(driver)

    return


def promoteStaff(driver, email_list):

    # For each address:
    for email in email_list:

        success = False
        
        # Structure:
        # <div class="course-team-member">
        #  <div class="member-info">
        #   <a>e-mail address</a>
        #  </div>
        #  <div class="member-actions">
        #   <button>Add admin access</button>
        #   <button data-testid="delete-button"></button>
        #  </div>
        # </div>

        # Find the "Add admin access" button for this user.
        promotion_xpath = (
            "//div[contains(@class, 'course-team-member')]"
            + "//div[contains(@class, 'member-info')]"
            + "//a[text()='"
            + email
            + "']"
            + "/ancestor::div[contains(@class, 'course-team-member')]"
            + "//div[contains(@class, 'member-actions')]"
            + "//button[text()='Add admin access']"
        )

        if userIsStaff(driver, email):

            # Keep trying up to 3 times in case we're still loading.
            for x in range(0, 3):
                log("Promoting " + email)
                try:
                    # Find the promotion button for this user.
                    promotion_button = driver.find_elements(
                        By.XPATH, promotion_xpath
                    )
                except:
                    log(
                        "No promotion button found. You may not have Admin access. Trying again...",
                        "WARNING",
                    )
                    continue
                try:
                    promotion_button[0].click()
                    success = True
                    break
                except Exception as e:
                    # log(repr(e), "DEBUG")
                    log("Couldn't click promotion button. Trying again...")
        else:
            if userIsAdmin(driver, email):
                log(email + " is already admin.")
            else:
                log(email + " is not in this course. Add them before promoting them.")

        if success:
            log("Promoted " + email + " to Admin.")
        else:
            log("Could not promote " + email)

    return


def removeStaff(driver, email_list):

    confirm_removal_xpath = "//button[text()='Delete']"

    # For each address:
    for email in email_list:

        # Structure:
        # <div class="course-team-member">
        #  <div class="member-info">
        #   <a>e-mail address</a>
        #  </div>
        #  <div class="member-actions">
        #   <button>Add admin access</button>
        #   <button data-testid="delete-button"></button>
        #  </div>
        # </div>

        # Find the delete button for this user.
        removal_xpath = (
            "//div[contains(@class, 'course-team-member')]"
            + "//div[contains(@class, 'member-info')]"
            + "//a[text()='"
            + email
            + "']"
            + "/ancestor::div[contains(@class, 'course-team-member')]"
            + "//div[contains(@class, 'member-actions')]"
            + "//button[@data-testid='delete-button']"
        )

        # If this user isn't present, move on to the next one.
        if not userIsPresent(driver, email):
            log(email + " was already not in this course.")
            continue

        success = False

        for x in range(0, 3):
            try:
                # E-mail addresses in the data attribute are lowercased.
                remove_button = driver.find_elements(
                    By.XPATH, removal_xpath
                )
                # Click the trash can ("remove user" button)
                remove_button[0].click()
                # Click the "confirm" button.
                log("Trying to remove " + email)
                confirm_button = driver.find_elements(
                    By.XPATH, confirm_removal_xpath
                )
                confirm_button[0].click()
                success = True
                break

            except Exception as e:
                # log(repr(e), "DEBUG")
                # Keep trying up to 3 times.
                log("Trying again...")

        if success:
            log("Removed " + email)
        else:
            log("Could not remove " + email)

    return


def demoteStaff(driver, email_list):

    # For each address:
    for email in email_list:

        success = False
        # Structure:
        # <div class="course-team-member">
        #  <div class="member-info">
        #   <a>e-mail address</a>
        #  </div>
        #  <div class="member-actions">
        #   <button>Remove admin access</button>
        #   <button data-testid="delete-button"></button>
        #  </div>
        # </div>

        # Find the delete button for this user.
        demotion_xpath = (
            "//div[contains(@class, 'course-team-member')]"
            + "//div[contains(@class, 'member-info')]"
            + "//a[text()='"
            + email
            + "']"
            + "/ancestor::div[contains(@class, 'course-team-member')]"
            + "//div[contains(@class, 'member-actions')]"
            + "//button[text()='Remove admin access']"
        )

        if userIsAdmin(driver, email):

            # Keep trying up to 3 times in case we're still loading.
            for x in range(0, 3):
                log("Demoting " + email)
                try:
                    # Find the demotion button for this user.
                    demotion_button = driver.find_elements(
                        By.XPATH, demotion_xpath
                    )
                except:
                    log(
                        "Couldn't find demotion button. You may not have Admin access. Trying again...",
                        "WARNING",
                    )
                    continue
                try:
                    demotion_button[0].click()
                    success = True
                    break
                except Exception as e:
                    # log(repr(e), "DEBUG")
                    log("Couldn't click demotion button. Trying again...")
        else:
            if userIsStaff(driver, email):
                log(email + " is already staff.")
            else:
                log(email + " is not in this course.")

        if success:
            log("Demoted " + email + " to staff.")
        else:
            log("Could not demote " + email)

    return


#######################
# Main starts here
#######################


def ReplaceEdXStaff():

    trimLog()

    num_classes = 0
    num_classes_fixed = 0
    skipped_classes = []
    staffed_classes = []
    unfound_addresses = []
    run_headless = True
    timeouts = 0
    too_many_timeouts = 3

    # Read in command line arguments.
    parser = argparse.ArgumentParser(usage=instructions, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-l", "--list", action="store_true")
    parser.add_argument("-v", "--visible", action="store_true")
    parser.add_argument("-f", "--firefox", action="store_true")
    parser.add_argument("-c", "--chrome", action="store_true")
    parser.add_argument("csvfile", default=None)

    args = parser.parse_args()
    if args.help or args.csvfile is None:
        sys.exit(instructions)

    run_headless = True
    if args.visible:
        run_headless = False

    driver_choice = "firefox"
    if args.chrome:
        log("Using Chrome instead of Firefox.")
        driver_choice = "chrome"

    if not os.path.exists(args.csvfile):
        sys.exit("Input file not found: " + args.csvfile)

    # Prompt for username and password
    # TODO: Maybe allow a file to read username and pw from.
    print(
        """
This script requires a username and password to run.
This user must have Admin status on all courses in which
the script is to run. Press control-C to cancel.
"""
    )
    username = input("User e-mail address: ")
    password = getpass()

    start_time = datetime.datetime.now()

    # Prep the web driver and sign into edX.
    driver = setUpWebdriver(run_headless, driver_choice)
    signIn(driver, username, password)

    # Open the csv and read it to a set of dicts
    with open(args.csvfile, "r") as file:

        log("Opening csv file.")
        reader = csv.DictReader(file)

        # For each line in the CSV...
        for each_row in reader:
            # log("Processing line:", "DEBUG")
            # log(each_row, "DEBUG")

            # Open the URL. Skip lines without one.
            if each_row["URL"] == "":
                continue

            num_classes += 1
            driver.get(each_row["URL"].strip())

            # Check to make sure we've opened a new page.
            # The e-mail input box should be invisible.
            try:
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located(
                        (By.CSS_SELECTOR, "input#user-email-input")
                    )
                )
                timeouts = 0
            except Exception as e:
                # log(repr(e), "DEBUG")
                # If we can't open the URL, make a note and skip this course.
                skipped_classes.append(each_row)
                if "Dashboard" in driver.title:
                    log("Course Team page load timed out for " + each_row["URL"])
                    skipped_classes.append(each_row)
                    timeouts += 1
                    if timeouts >= too_many_timeouts:
                        log(
                            str(too_many_timeouts)
                            + " course pages timed out in a row.",
                            "WARNING",
                        )
                        log(
                            "Check URLs and internet connectivity and try again.",
                            "WARNING",
                        )
                        break
                continue

            # If we only need to get users and status, we can do that easier.
            if args.list:
                log("Getting staff for " + each_row["URL"])
                user_list = getAllUsers(driver)
                # log(user_list)
                this_class = {
                    "Course": each_row["Course"],
                    "URL": each_row["URL"],
                    "Admin": " ".join(user_list["admin"]),
                    "Staff": " ".join(user_list["staff"]),
                }
                staffed_classes.append(this_class)
                continue

            # Check to make sure we have the ability to change user status.
            if not userIsAdmin(driver, username):
                log("\nUser is not admin in " + each_row["URL"])
                skipped_classes.append(each_row)
                continue

            if (
                "Course team" not in driver.title
                or "Forbidden" in driver.title
            ):
                log("\nCould not open course " + each_row["URL"])
                skipped_classes.append(each_row)
                continue

            log("\n" + driver.title)
            log(each_row["URL"])
            # Functions to call for each task. As of Python 3.6 they'll stay in this order.
            jobs = {
                "Add": addStaff,
                "Promote": promoteStaff,
                "Remove": removeStaff,
                "Demote": demoteStaff,
            }
            for j in jobs:
                if each_row[j] is None:
                    driver.quit()
                    log("CSV error - might be missing a column.", "CRITICAL")
                    continue
                # Taking out whitespace.
                # Split e-mail list on spaces and throw out blank elements.
                email_list_with_blanks = each_row[j].split(" ")
                email_list = [x for x in email_list_with_blanks if x != ""]
                email_list = [x.strip() for x in email_list]
                if len(each_row[j]) > 0:
                    jobs[j](driver, email_list)
                    # You have to wait because I don't even know why.
                    # Otherwise it skips lines - sometimes up to half of them.
                    time.sleep(2)

        # Done with the webdriver.
        driver.quit()

        # In list mode, save a CSV with our course staff.
        if args.list:
            log(
                "See course_staffing.csv for a full list of course staff and administrators."
            )
            with open("course_staffing.csv", "w", newline="") as all_staff:
                fieldnames = ["Course", "URL", "Admin", "Staff"]
                writer = csv.DictWriter(all_staff, fieldnames=fieldnames)

                writer.writeheader()
                for x in staffed_classes:
                    writer.writerow(x)
        # Write out a new csv with the ones we couldn't do.
        else:
            if len(skipped_classes) > 0:
                log("See remaining_courses.csv for courses that had to be skipped.")
                with open(
                    "remaining_courses.csv", "w", newline=""
                ) as remaining_courses:
                    fieldnames = ["Course", "URL", "Add", "Promote", "Remove", "Demote"]
                    writer = csv.DictWriter(
                        remaining_courses, fieldnames=fieldnames, extrasaction="ignore"
                    )

                    writer.writeheader()
                    for x in skipped_classes:
                        writer.writerow(x)

        log("Processed " + str(num_classes - len(skipped_classes)) + " courses")
        end_time = datetime.datetime.now()
        log("in " + str(end_time - start_time).split(".")[0])

    # Done.


if __name__ == "__main__":
    ReplaceEdXStaff()
