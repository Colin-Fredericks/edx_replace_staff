# VPAL Multi-course Staffing Script

import os
import csv
import sys
import time
import argparse
from getpass import getpass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# TODO: Better tracking of what we had to skip.
# TODO: Handle errors on add

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
and which people couldn't be removed.
"""


# Instantiating a headless Chrome browser
def setUpWebdriver():
    print("Setting up webdriver.")
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + "."
    c = Options()
    # c.add_argument("--headless")
    driver = webdriver.Chrome(options=c)
    driver.implicitly_wait(2)
    return driver


def signIn(driver, username, password):

    # Locations
    login_page = "https://authn.edx.org/login"
    username_input_css = "#emailOrUsername"
    password_input_css = "#password"
    login_button_css = ".login-button-width"

    # Open the edX sign-in page
    print("Logging in...")
    driver.get(login_page)

    # Sign in
    username_field = driver.find_elements(By.CSS_SELECTOR, username_input_css)[0]
    username_field.clear()
    username_field.send_keys(username)
    password_field = driver.find_elements(By.CSS_SELECTOR, password_input_css)[0]
    password_field.clear()
    password_field.send_keys(password)
    login_button = driver.find_elements(By.CSS_SELECTOR, login_button_css)[0]
    login_button.click()

    # Check to make sure we're signed in
    try:
        found_dashboard = WebDriverWait(driver, 10).until(
            EC.title_contains("Dashboard")
        )
    except:
        driver.close()
        if "Forbidden" in driver.title:
            sys.exit("403: Forbidden")
        if "Login" in driver.title:
            sys.exit("Took too long to log in.")
        sys.exit("Could not log into edX or course dashboard page timed out.")

    print("Logged in.")
    return


def addStaff(driver, email_list):

    # Locations for add-staff inputs
    new_team_css = "a.create-user-button"
    new_staff_email_css = "input#user-email-input"
    add_user_css = "div.actions button.action-primary"
    wrong_email_css = "#prompt-error.is-shown"
    already_on_team_css = "#prompt-warning.is-shown"
    ok_button_css = "button.action-primary"

    # For each address:
    for email in email_list:
        keep_going = True
        loops = 0
        max_loops = 3
        while keep_going:
            print("Adding " + email)
            try:
                # Click the "New Team Member" button
                new_team_button = driver.find_elements(By.CSS_SELECTOR, new_team_css)[0]
                new_team_button.click()
                # Put the e-mail into the input box.
                email_box = driver.find_elements(By.CSS_SELECTOR, new_staff_email_css)[
                    0
                ]
                email_box.clear()
                email_box.send_keys(email)
                # Click "Add User"
                add_user_button = driver.find_elements(By.CSS_SELECTOR, add_user_css)[0]
                add_user_button.click()

                # TODO: This part isn't working. Not sure why.
                # If there's an error message, it's fine. Click the "ok" button.
                wrong_email_alert = driver.find_elements(
                    By.CSS_SELECTOR, wrong_email_css
                )
                already_on_team_alert = driver.find_elements(
                    By.CSS_SELECTOR, already_on_team_css
                )
                if len(wrong_email_alert) > 0:
                    print("No user with email " + email)
                    ok_button = driver.findElements(
                        By.CSS_SELECTOR, wrong_email_css + " " + ok_button_css
                    )
                    ok_button[0].click()
                    continue
                elif len(already_on_team_alert) > 0:
                    ok_button = driver.findElements(
                        By.CSS_SELECTOR, already_on_team_css + " " + ok_button_css
                    )
                    ok_button[0].click()
                    print(email + " is already on the team.")
                    continue

                keep_going = False

            except Exception as e:
                print(repr(e))
                # Keep trying up to 3 times.
                print("Trying again...")
                loops = loops + 1
                if loops > max_loops:
                    keep_going = False

    return


def promoteStaff(driver, email_list):
    # For each address:
    for email in email_list:
        # Find the promotion button for this user.
        promotion_css = (
            "li[data-email='"
            + email.lower()
            + "'] a.make-instructor.admin-role.add-admin-role"
        )
        keep_going = True
        loops = 0
        max_loops = 3

        while keep_going:
            print("Promoting " + email)
            try:
                # Click the "New Team Member" button
                promotion_button = driver.find_elements(By.CSS_SELECTOR, promotion_css)
                promotion_button[0].click()
                keep_going = False
            except Exception as e:
                print(repr(e))
                # Keep trying up to 3 times.
                print("Trying again...")
                loops = loops + 1
                if loops > max_loops:
                    keep_going = False

    return


def removeStaff(driver, email_list):

    # The "remove" button is a link inside an LI.
    # The LI has data-email equal to the user's email address.
    trash_can_css = "a.remove-user"
    confirm_removal_css = "#prompt-warning.is-shown button.action-primary"

    # For each address:
    for email in email_list:
        removal_button_css = "li[data-email='" + email.lower() + "'] " + trash_can_css
        keep_going = True
        loops = 0
        max_loops = 3
        while keep_going:
            print("Finding " + email)
            try:
                # E-mail addresses in the data attribute are lowercased.
                remove_button = driver.find_elements(
                    By.CSS_SELECTOR, removal_button_css
                )
                # Click the trash can ("remove user" button)
                remove_button[0].click()
                # Click the "confirm" button.
                print("Removing " + email)
                confirm_button = driver.find_elements(
                    By.CSS_SELECTOR, confirm_removal_css
                )
                confirm_button[0].click()
                keep_going = False

            except Exception as e:
                print(repr(e))
                # Keep trying up to 3 times.
                print("Trying again...")
                loops = loops + 1
                if loops > max_loops:
                    print(email + " was already not in this course.")
                    keep_going = False

    return


def demoteStaff(driver, email_list):
    # For each address:
    for email in email_list:
        # Find the demotion button for this user.
        demotion_css = (
            "li[data-email='"
            + email.lower()
            + "'] a.make-staff.admin-role.remove-admin-role"
        )
        keep_going = True
        loops = 0
        max_loops = 3

        while keep_going:
            print("Demoting " + email)
            try:
                # Click the "New Team Member" button
                demotion_button = driver.find_elements(By.CSS_SELECTOR, demotion_css)
                demotion_button[0].click()
                keep_going = False
            except Exception as e:
                print(repr(e))
                # Keep trying up to 3 times.
                print("Trying again...")
                loops = loops + 1
                if loops > max_loops:
                    keep_going = False

    return


#######################
# Main starts here
#######################


def ReplaceEdXStaff():

    num_classes = 0
    num_classes_fixed = 0
    skipped_classes = []
    unfound_addresses = []

    # Read in command line arguments.
    parser = argparse.ArgumentParser(usage=instructions, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("csvfile", default=None)

    args = parser.parse_args()
    if args.help or args.csvfile is None:
        sys.exit(instructions)

    if not os.path.exists(args.csvfile):
        sys.exit("Input file not found: " + args.csvfile)

    # Prompt for username and password
    print(
        """
This script requires a username and password to run.
This user must have Admin status on all courses in which
the script is to run. Press control-C to cancel.
"""
    )
    username = input("Username: ")
    password = getpass()

    # Prep the web driver and sign into edX.
    driver = setUpWebdriver()
    signIn(driver, username, password)

    # Open the csv and read it to a set of dicts
    with open(args.csvfile, "r") as file:
        print("Opening csv file.")
        reader = csv.DictReader(file)

        # For each line in the CSV...
        for each_row in reader:
            # print("Processing line:")
            # print(each_row)
            num_classes += 1

            # Open the URL.
            driver.get(each_row["URL"].strip())

            # Check to make sure we've opened a new page.
            # The e-mail input box should be invisible.
            try:
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located(
                        (By.CSS_SELECTOR, "input#user-email-input")
                    )
                )
            except Exception as e:
                print(repr(e))
                # If we can't open the URL, make a note and skip this course.
                skipped_classes.append(each_row)
                if "Forbidden" in driver.title:
                    print("Could not open course " + each_row["URL"])
                if "Dashboard" in driver.title:
                    print("Course Team page load timed out.")
                continue

            print(driver.title)
            # Functions to call for each task. As of Python 3.6 they'll stay in this order.
            jobs = {
                "Add": addStaff,
                "Promote": promoteStaff,
                "Remove": removeStaff,
                "Demote": demoteStaff,
            }
            for j in jobs:
                # Taking out whitespace.
                # Split e-mail list on spaces and throw out blank elements.
                email_list_with_blanks = each_row[j].split(" ")
                email_list = [x for x in email_list_with_blanks if x != ""]
                if len(each_row[j]) > 0:
                    jobs[j](driver, email_list)
                    # You have to wait because I don't even know why.
                    # Otherwise it skips lines - sometimes up to half of them.
                    time.sleep(2)

        # Write out a new csv with the ones we couldn't do.
        if len(skipped_classes) > 0:
            with open("remaining_courses.csv", "w", newline="") as remaining_courses:
                fieldnames = ["Course", "URL", "Add", "Promote", "Remove", "Demote"]
                writer = csv.DictWriter(remaining_courses, fieldnames=fieldnames)

                writer.writeheader()
                for x in skipped_classes:
                    writer.writerow(x)
        else:
            print("Total: " + str(num_classes) + " courses.")

    # Done.
    driver.quit()


if __name__ == "__main__":
    ReplaceEdXStaff()
