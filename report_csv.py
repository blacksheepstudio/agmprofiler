import yaml
import gspread
from gspread.exceptions import APIError
import string
from oauth2client.service_account import ServiceAccountCredentials
import os
from agm_profiler import *
import json


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_PATH = SCRIPT_DIR + '/creds/client_secret.json'
ENDPOINTS = ('/cluster', '/consistencygroup', '/logicalgroup', '/jobstatus', '/application',
             '/slt', '/slp', '/host', '/user', '/role', '/org', '/diskpool', '/backup')


class YamlLoader(object):
    @staticmethod
    def load_yml(filepath):
        return yaml.load(open(filepath))


class SheetsConnection(object):
    def __init__(self, sheet_name, tab_index=0, credentials_json_path=''):
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        # scope = ['https://www.googleapis.com/auth/spreadsheets']
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_json_path, scope)
        print(creds)
        self.client = gspread.authorize(creds)
        # self.sheet = getattr(self.client.open(sheet_name), tab_name)
        self.spreadsheet = self.client.open(sheet_name)
        self.sheet = self.spreadsheet.get_worksheet(tab_index)
        # Creates list of column names A-Z, then AA, AB, AC, AD etc.
        self.cell_column_names = list(string.ascii_uppercase) + ['A' + letter for letter in string.ascii_uppercase] + \
                                 ['B' + letter for letter in string.ascii_uppercase]

    def get_all_records(self):
        return self.sheet.get_all_records()

    def _dir_sheet(self):
        return dir(self.sheet)

    def next_available_row(self):
        str_list = list(filter(None, self.sheet.col_values(1)))
        return str(len(str_list) + 1)

    def append_to_sheet(self, row_values):
        """
        :param row_values: list of values, where each item in the list is a column value in this row
        :return:
        """
        # TODO : This is a hacky way of handling APIErrors, refactor this later
        api_errors_excepted = 0

        next_row = self.next_available_row()
        for i, value in enumerate(row_values):
            cell_to_update = f'{self.cell_column_names[i]}{next_row}'
            print(f'Updating cell: {cell_to_update}')
            try:
                self.sheet.update_acell(cell_to_update, value)
            except APIError:
                if api_errors_excepted < 3:
                    print('Encountered API Error, sleeping 100 seconds and retrying')
                    time.sleep(101)
                    self.sheet.update_acell(cell_to_update, value)
                    api_errors_excepted += 1
                else:
                    raise


class ResultCSVUpdater(object):
    def __init__(self, spreadsheetname='System Test Results', spreadsheettab=0, secret_file=''):
        """
        :param spreadsheetname: Name of the share spreadsheet on google sheets
        :param list_of_lists: list of lists where each sublist is a row
        """
        self.sc = SheetsConnection(spreadsheetname, spreadsheettab, secret_file)

    def append_to_csv(self, rows, header=None):
        if header:
            self.sc.append_to_sheet(header)
        for row in rows:
            print(row)
            self.sc.append_to_sheet(row)


def create_json_file(result_obj_li, json_filename='output.json'):
    """ Takes a list of CallTestResponse and creates a json file of results """
    data_list = list()
    for result_obj in result_obj_li:
        data_list.append(result_obj._data)
    print(data_list)
    with open(json_filename, 'w') as f:
        json.dump(data_list, f)


def run_get_list_test(ipaddress, username, password, spreadsheet='System Test Results', tab=2, include_header=False,
                      json_filename='output_get_list.json'):
    print('RUNNING GET LIST TEST')
    a = APICallTester(ipaddress, username, password)
    a.agm_login()
    result_obj_li = a.time_calls(ENDPOINTS)
    # results_li = [list(obj) for obj in result_obj_li]
    header, single_row = single_row_format(result_obj_li)
    # Update GET List calls
    updater = ResultCSVUpdater(spreadsheet, tab, SECRET_PATH)

    print(f'outputing to {json_filename}')
    create_json_file(result_obj_li, json_filename)

    # updater.append_to_csv(results_li)
    if not include_header:
        updater.append_to_csv([single_row])
    else:
        updater.append_to_csv([header, single_row])


def run_get_detail_test(ipaddress, username, password, spreadsheet='System Test Results', tab=3, include_header=False,
                        json_filename='output_get_detail.json'):
    print('RUNNING GET DETAIL TEST')
    a = APICallTester(ipaddress, username, password)
    a.agm_login()
    result_obj_li = a.time_detail_calls(ENDPOINTS)
    # results_li = [list(obj) for obj in result_obj_li]
    header, single_row = single_row_format(result_obj_li)
    # Update GET List calls
    updater = ResultCSVUpdater(spreadsheet, tab, SECRET_PATH)

    print(f'outputing to {json_filename}')
    create_json_file(result_obj_li, json_filename)

    # updater.append_to_csv(results_li)
    if not include_header:
        updater.append_to_csv([single_row])
    else:
        updater.append_to_csv([header, single_row])


def create_huge_dataset(ipaddress, username, password, iterations=5):
    for i in range(0, iterations):
        print(f'***** ITERATION NUMBER: {i}')
        run_get_list_test(ipaddress, username, password, json_filename=f'result_list{i}.json')
        run_get_detail_test(ipaddress, username, password, json_filename=f'result_detail{i}.json')


if __name__ == '__main__':
    # ipaddress = '172.17.139.215'
    ipaddress = '172.27.6.99'
    username = 'admin'
    password = 'password'
    # run_get_list_test(ipaddress, username, password)
    # run_get_detail_test(ipaddress, username, password)
    create_huge_dataset(ipaddress, username, password)