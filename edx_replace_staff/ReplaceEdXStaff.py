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
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.wait import WebDriverWait
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
  -h or --help:     Print this message and exit.
  -l or --list:     List all staff and admin in all courses. Make no changes.
                    Only requires the URL column.
  -c or --chrome:   Use Chrome instead of default Firefox.
  -v or --visible:  Run the browser in normal mode instead of headless.
  --cs50:           Include CS50 courses. By default, they are skipped.

"""

# Prep the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s : %(funcName)s : %(levelname)s : %(message)s"
)

file_handler = logging.FileHandler("edx_staffing.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

screen_handler = logging.StreamHandler()
screen_handler.setFormatter(formatter)
logger.addHandler(screen_handler)


def trimLog(log_file="edx_staffing.log", max_lines=20000) -> None:
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
def setUpWebdriver(run_headless: bool, driver_choice: str = "firefox") -> WebDriver:
    """
    Sets up a Chrome or Firefox browser.

    Parameters:
    run_headless (bool): Whether to run the browser in headless mode.
    driver_choice (str): Which browser to use. Default is firefox, "chrome" is an option.
    """
    logger.info("Setting up webdriver.")
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + os.path.dirname(__file__)

    # Check to make sure the repo is in the right place. If not, prompt for it.
    repo_path = "/Users/" + os.getlogin() + "/Documents/GitHub/edx_replace_staff/"
    if not os.path.exists(repo_path):
        prompt = (
            "The edx_replace_staff repo is not in its usual location.\n"
            + "Please enter the full path to the repo, starting from your root directory: "
        )
        repo_path = input(prompt)
        if not os.path.exists(repo_path):
            sys.exit("Cannot proceed. The path you entered does not exist.")

    if driver_choice == "chrome":
        op = ChromeOptions()
        op.add_argument("start-maximized")
        op.timeouts = {"implicit": 1000}
        if run_headless:
            op.add_argument("--headless")
        webdriver.ChromeService(
            executable_path=os.path.join(repo_path, "edx_replace_staff/chromedriver")
        )
        driver = webdriver.Chrome(options=op)
    else:
        op = FirefoxOptions()
        op.binary_location = "/Applications/Firefox.app/Contents/MacOS/firefox"
        op.timeouts = {"implicit": 1000}
        if run_headless:
            op.add_argument("-headless")
        webdriver.FirefoxService(
            executable_path=os.path.join(repo_path, "edx_replace_staff/geckodriver")
        )
        driver = webdriver.Firefox(options=op)

    return driver


def signIn(driver: WebDriver, username: str, password: str) -> None:
    """Signs into edx.org"""
    # Locations
    login_page = "https://authn.edx.org/login"
    username_input_css = "#emailOrUsername"
    password_input_css = "#password"
    login_button_css = "#sign-in"

    # Open the edX sign-in page
    logger.info("Logging in...")
    driver.get(login_page)

    # Wait a second.
    time.sleep(1)

    # Apparently we have to run this more than once sometimes.
    login_count = 0
    while login_count < 3:
        # Sign in
        try:
            WebDriverWait(driver, 10).until(
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
        logger.info("Username sent")

        # Wait a second.
        time.sleep(1)

        password_field = driver.find_elements(By.CSS_SELECTOR, password_input_css)[0]
        password_field.clear()
        password_field.send_keys(password)
        logger.info("Password sent")

        # Wait a second.
        time.sleep(1)

        # Using ActionChains is necessary because edX put a div over the login button.
        login_button = driver.find_elements(By.CSS_SELECTOR, login_button_css)[0]
        actions = ActionChains(driver)
        actions.move_to_element(login_button).click().perform()
        logger.info("Login button clicked")

        # Check to make sure we're signed in.
        # There are several possible fail states to check for.
        found_dashboard = False
        try:
            logger.info("Finding dashboard...")
            found_dashboard = WebDriverWait(driver, 10).until(EC.url_contains("home"))
        except (
            selenium_exceptions.TimeoutException,
            selenium_exceptions.InvalidSessionIdException,
        ):
            logger.debug(str(traceback.print_exc()), "WARNING")
            login_fail = driver.find_elements(By.CSS_SELECTOR, "#login-failure-alert")
            if len(login_fail) > 0:
                logger.info("Incorrect login or password")
            need_reset = driver.find_elements(
                By.CSS_SELECTOR, "#password-security-reset-password"
            )
            if len(need_reset) > 0:
                logger.error("Password reset required")
            if "Forbidden" in driver.title:
                logger.error("403: Forbidden")

        # If we're logged in, we're done.
        if found_dashboard:
            logger.info("Logged in.")
            return

        login_count += 1
        logger.info("Login attempt count: " + str(login_count))

    driver.close()
    logger.error("Login failed.")
    sys.exit("Login issue or course dashboard page timed out.")


def userIsPresent(driver: WebDriver, email: str) -> bool:
    """Checks to see if user is already on course team. Returns boolean."""
    logger.debug("Is " + email + " present?")

    is_staff_xpath = "//a[contains(@href,'" + email.lower() + "')]"
    user_present = driver.find_elements(By.XPATH, is_staff_xpath)
    if len(user_present) > 0:
        logger.debug(email + " is on the course team.")
        return True
    else:
        logger.debug(email + " is not on the course team.")
        return False


def userIsStaff(driver: WebDriver, email: str) -> bool:
    """Checks to see if user is staff. Returns boolean."""
    staff_user_xpath = (
        "//span[contains(@class, 'badge-current-user') and contains(text(), 'Staff')]"
        + "//following-sibling::a[contains(@href, '"
        + email.lower()
        + "')]"
    )
    staff_flag = driver.find_elements(By.XPATH, staff_user_xpath)
    if len(staff_flag) > 0:
        logger.debug(email + " is staff.")
        return True
    else:
        logger.debug(email + " is not staff.")
        return False


def userIsAdmin(driver: WebDriver, email: str) -> bool:
    """
    Checks to see whether the user we're signed in as is admin.
    If not, we can't do anything - you need to be admin to make changes.
    Returns boolean.
    """

    # Xpath to find the admin flag for this user.
    is_admin_xpath = (
        "//span[contains(@class, 'badge-current-user') and contains(text(), 'Admin')]"
        + "//following-sibling::a[contains(@href, '"
        + email.lower()
        + "')]"
    )

    admin_flag = driver.find_elements(By.XPATH, is_admin_xpath)
    if len(admin_flag) > 0:
        logger.debug(email + " is admin.")
        return True
    else:
        logger.debug(email + " is not admin.")
        return False


def getAllUsers(driver: WebDriver) -> dict:
    """
    Returns a dictionary with two lists of e-mail addresses: staff and admin.
    """

    staff_xpath = "//span[contains(@class, 'badge-current-user') and contains(text(), 'Staff')]/following-sibling::a"
    admin_xpath = "//span[contains(@class, 'badge-current-user') and contains(text(), 'Admin')]/following-sibling::a"

    all_staff = driver.find_elements(By.XPATH, staff_xpath)
    all_admins = driver.find_elements(By.XPATH, admin_xpath)
    staff_list = [x.text for x in all_staff]
    admin_list = [y.text for y in all_admins]

    return {"staff": staff_list, "admin": admin_list}


def closeErrorDialog(driver: WebDriver) -> dict:
    """
    Closes error dialogs on the course staff page. Can't go on without that.

    Returns info about the dialog.
        If there was none, it's "no_dialog"
        If we closed it and they weren't a user, it's "no_user"
        If we couldn't close the dialog, it's "failed_to_close"
    """

    logger.debug("Checking for error dialog")

    # Try to find the "ok" button for the error dialogs.
    wrong_email_css = "div[aria-label='Error adding user'] button"

    # If there is an error dialog open, report why, clear it, and move on.
    try:
        logger.debug("Finding error dialog")
        wrong_email_ok_button = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, wrong_email_css))
        )
        if wrong_email_ok_button is None:
            logger.debug("No error dialog found.")
            return {"reason": "no_dialog"}
        else:
            logger.debug("Error dialog found.")
    except Exception:
        # If there was no error dialog, we can move on.
        logger.debug("No error dialog found.")
        return {"reason": "no_dialog"}

    try:
        # No user with specified e-mail address.
        # (At least, that's the only current error shown.)
        wrong_email_ok_button.click()
        return {"reason": "no_user"}
    except Exception as e:
        # Couldn't close the error dialog.
        logger.warning("Could not close error dialog for " + driver.title)
        logger.debug(str(e))
        return {"reason": "failed_to_close"}


def addStaff(driver: WebDriver, email_list: list[str]) -> None:
    """Adds a list of users as course staff via e-mail address. You can promote them to admin later."""

    # Locations for add-staff inputs
    new_team_xpath = "//button[text()='New team member']"
    new_staff_email_xpath = "//input[@name='email']"
    add_user_xpath = "//button[text()='Add user']"

    logger.info("Adding staff to " + driver.title)

    # For each address:
    for email in email_list:
        logger.info("Adding " + email)

        # If the user is already present, move to the next e-mail address.
        if userIsPresent(driver, email):
            logger.debug(email + " is already on course team.")
            continue
        else:
            logger.debug(email + " is not on course team yet.")

        # Retry up to 3 times.
        success = False
        for x in range(0, 3):
            try:
                # Click the "New Team Member" button
                new_team_buttons = driver.find_elements(By.XPATH, new_team_xpath)
                new_team_buttons[0].click()
                logger.debug("Clicked 'New Team Member'")
            except Exception:
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
                    # Clear the dialog and try again (or move on).
                    closeErrorDialog(driver)

            except Exception:
                # If the stuff above failed, it's probably because
                # one of the elements hasn't been added to the page yet.
                logger.warning("Couldn't add " + email + ", trying again...")
                # logger.debug(repr(e))

        if success:
            logger.info("Successfully added " + email)
        else:
            logger.info("Could not add " + email)
            closeErrorDialog(driver)

    return


def promoteStaff(driver: WebDriver, email_list: list[str]) -> None:
    """Promotes a list of staff users to admin."""

    # For each address:
    for email in email_list:
        logger.info("Promoting " + email)

        success = False

        # Find the "Add admin access" button for this user.
        promotion_xpath = (
            "//a[contains(@href, '"
            + email.lower()
            + "')]/ancestor::div[contains(@class, 'member-info')]"
            + "//following-sibling::div[contains(@class, 'member-actions')]"
            + "//button[contains(text(), 'Add admin access')]"
        )

        if userIsStaff(driver, email):
            # Keep trying up to 3 times in case we're still loading.
            for x in range(0, 3):
                try:
                    # Find the promotion button for this user.
                    promotion_button = driver.find_elements(By.XPATH, promotion_xpath)
                except Exception:
                    logger.warning(
                        "No promotion button found. You may not have Admin access. Trying again..."
                    )
                    continue
                try:
                    promotion_button[0].click()
                    success = True
                    break
                except Exception:
                    logger.debug("Couldn't click promotion button. Trying again...")
        else:
            if userIsAdmin(driver, email):
                logger.debug(email + " is already admin.")
            else:
                logger.debug(
                    email + " is not in this course. Add them before promoting them."
                )

        if success:
            logger.info("Promoted " + email + " to Admin.")
        else:
            logger.info("Could not promote " + email)

    return


def removeStaff(driver: WebDriver, email_list: list[str]) -> None:
    """
    Removes a list of users from the course staff.
    If they're admin you have to demote them first.
    """

    logger.info("Removing staff from " + driver.title)

    confirm_removal_xpath = "//div[contains(@aria-label, 'Delete course team member')]//button[text()='Delete']"

    # For each address:
    for email in email_list:
        logger.debug("Removing " + email)

        # If this user isn't present, move on to the next one.
        if not userIsPresent(driver, email):
            logger.debug(email + " was already not in this course.")
            continue

        # Find the delete button for this user.
        removal_xpath = (
            "//div[contains(@class, 'course-team-member')]"
            + "//div[contains(@class, 'member-info')]"
            + "//a[text()='"
            + email.lower()
            + "']"
            + "/ancestor::div[contains(@class, 'course-team-member')]"
            + "//div[contains(@class, 'member-actions')]"
            + "//button[@data-testid='delete-button']"
        )

        success = False

        for x in range(0, 3):
            try:
                # E-mail addresses in the data attribute are lowercased.
                remove_button = driver.find_elements(By.XPATH, removal_xpath)
                # Click the trash can ("remove user" button)
                remove_button[0].click()
                # Click the "confirm" button.
                logger.debug("Trying to remove " + email)
                confirm_button = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, confirm_removal_xpath))
                )
                confirm_button.click()
                success = True
                break

            except Exception:
                # logger.debug(repr(e))
                # Keep trying up to 3 times.
                logger.debug("Trying again...")

        if success:
            logger.info("Removed " + email)
        else:
            logger.info("Could not remove " + email)

    return


def demoteStaff(driver: WebDriver, email_list: list[str]) -> None:
    """Demotes a list of admin users to staff."""

    logger.info("Demoting staff in " + driver.title)

    # For each address:
    for email in email_list:
        logger.debug("Demoting " + email)

        success = False

        # Find the delete button for this user.
        demotion_xpath = (
            "//a[contains(@href, '"
            + email.lower()
            + "')]/ancestor::div[contains(@class, 'member-info')]"
            + "//following-sibling::div[contains(@class, 'member-actions')]"
            + "//button[contains(text(), 'Remove admin access')]"
        )

        if userIsAdmin(driver, email):
            # Keep trying up to 3 times in case we're still loading.
            for x in range(0, 3):
                try:
                    # Find the demotion button for this user.
                    demotion_button = driver.find_elements(By.XPATH, demotion_xpath)
                except Exception:
                    logger.warning(
                        "Couldn't find demotion button. You may not have Admin access. Trying again..."
                    )
                    continue
                try:
                    demotion_button[0].click()
                    success = True
                    break
                except Exception:
                    logger.debug("Couldn't click demotion button. Trying again...")
        else:
            if userIsStaff(driver, email):
                logger.debug(email + " is already staff.")
            else:
                logger.debug(email + " is not in this course.")

        if success:
            logger.info("Demoted " + email + " to staff.")
        else:
            logger.info("Could not demote " + email)

    return


#######################
# Main starts here
#######################


def ReplaceEdXStaff():
    trimLog()

    num_classes = 0
    skipped_classes = []
    staffed_classes = []
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
    parser.add_argument("--cs50", action="store_true")
    parser.add_argument("csvfile", default=None)

    args = parser.parse_args()
    if args.help or args.csvfile is None:
        sys.exit(instructions)

    run_headless = True
    if args.visible:
        run_headless = False

    driver_choice = "firefox"
    if args.chrome:
        logger.info("Using Chrome instead of Firefox.")
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

    """
    # We have to open the Studio outline in order to avoid CORS issues for some reason.
    driver.get("https://studio.edx.org/home")
    # This redirects to https://course-authoring.edx.org/home , but we actually want to get the redirect!
    # When the input with id pgn-searchfield-input-1 shows up we're good to continue.
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "pgn-searchfield-input-1"))
        )
    except selenium_exceptions.TimeoutException:
        logger.error("Studio page load timed out.")
        driver.quit()
        sys.exit("Studio page load timed out.")
    """

    # Open the csv and read it to a set of dicts
    with open(args.csvfile, "r") as file:
        logger.info("Opening csv file.")
        reader = csv.DictReader(file)

        # For each line in the CSV...
        for each_row in reader:
            # logger.debug("Processing line:")
            # logger.debug(each_row)

            if each_row["URL"] == "":
                continue

            # Skip CS50 courses unless we've specifically asked to include them.
            if "cs50" in each_row["URL"].lower() and not args.cs50:
                logger.info("Skipping CS50 course " + each_row["URL"])
                skipped_classes.append(each_row)
                continue

            # Skip pre-2015 URL patterns that will no longer work.
            # The newer one has a + instead of a /
            if "HarvardX/" in each_row["URL"]:
                logger.info("Skipping course with old URL scheme: " + each_row["URL"])
                skipped_classes.append(each_row)
                continue

            driver.get(each_row["URL"].strip())
            num_classes += 1

            # Check to make sure we've opened a new page.
            # The e-mail input box should be invisible.
            try:
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located(
                        (By.CSS_SELECTOR, "input#user-email-input")
                    )
                )
                timeouts = 0
            except Exception:
                # logger.debug(repr(e))
                # If we can't open the URL, make a note and skip this course.
                skipped_classes.append(each_row)
                if "Dashboard" in driver.title:
                    logger.warning(
                        "Course Team page load timed out for " + each_row["URL"]
                    )
                    skipped_classes.append(each_row)
                    timeouts += 1
                    if timeouts >= too_many_timeouts:
                        logger.warning(
                            str(too_many_timeouts) + " course pages timed out in a row."
                        )
                        logger.warning(
                            "Check URLs and internet connectivity and try again."
                        )
                        break
                continue

            # If we only need to get users and status, we can do that easier.
            if args.list:
                logger.info("Getting staff for " + each_row["URL"])
                user_list = getAllUsers(driver)
                # logger.debug(user_list)
                this_class = {
                    "Course": each_row["Course"],
                    "URL": each_row["URL"],
                    "Admin": " ".join(user_list["admin"]),
                    "Staff": " ".join(user_list["staff"]),
                }
                staffed_classes.append(this_class)
                continue

            # Check to make sure we have the ability to change user status.
            if not userIsAdmin(driver, username.lower()):
                logger.warning("\nUser is not admin in " + each_row["URL"])
                skipped_classes.append(each_row)
                continue

            if "Course team" not in driver.title or "Forbidden" in driver.title:
                logger.warning("\nCould not open course " + each_row["URL"])
                skipped_classes.append(each_row)
                continue

            logger.info("\n" + driver.title)
            logger.info(each_row["URL"])
            # Functions to call for each task. As of Python 3.6 they'll stay in this order.
            jobs = {
                "Add": addStaff,
                "Promote": promoteStaff,
                "Demote": demoteStaff,
                "Remove": removeStaff,
            }
            for j in jobs:
                if each_row[j] is None:
                    driver.quit()
                    logger.error("CSV error - might be missing a column.")
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
            logger.info(
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
                logger.info(
                    "See remaining_courses.csv for courses that had to be skipped."
                )
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

        logger.info("Processed " + str(num_classes - len(skipped_classes)) + " courses")
        end_time = datetime.datetime.now()
        logger.info("in " + str(end_time - start_time).split(".")[0])

    # Done.


if __name__ == "__main__":
    ReplaceEdXStaff()
