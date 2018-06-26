from actagm.agm_helper import AgmHelper
import time
import pprint
import logging
import os
import json


logging.basicConfig(level=logging.INFO)


ENDPOINTS = ('/cluster', '/consistencygroup', '/logicalgroup', '/jobstatus', '/application',
             '/slt', '/slp', '/host', '/user', '/role', '/org', '/diskpool', '/backup')


# ENDPOINTS = ('/cluster', '/consistencygroup', '/logicalgroup', '/jobstatus')
JSON_FILENAME = 'agm_data.json'

# /cluster may have 'stale' field in response, where timeout occured and we were unable to get all the data


class APICallTester(object):
    def __init__(self, *args, **kwargs):
        self.ah = AgmHelper(*args, **kwargs)

    def time_calls(self, endpoints, iterations=10):
        """
        Given the list of endpoints, tests each endpoint for N iterations and returns the average time
        for each endpoint to get a response.

        :param endpoints: list of endpoints like ['/application', '/host', '/slt']
        :param iterations: number of times to attempt each call
        :return: list of run CallTestResponse objects
        """
        test_result_list = list()
        for endpoint in endpoints:
            call_test_response = CallTestResponse(self, endpoint, iterations)
            call_test_response.run_list()
            logging.info(call_test_response)
            test_result_list.append(call_test_response)
        return test_result_list

    def time_detail_calls(self, endpoints, iterations=10):
        test_result_list = list()
        for endpoint in endpoints:
            call_test_response = CallTestResponse(self, endpoint, iterations)
            call_test_response.run_detail()
            logging.info(call_test_response)
            test_result_list.append(call_test_response)
        return test_result_list

    def time_head_calls(self, endpoints, iterations=10):
        test_result_list = list()
        for endpoint in endpoints:
            call_test_response = CallTestResponse(self, endpoint, iterations)
            call_test_response.run_head()
            logging.info(call_test_response)
            test_result_list.append(call_test_response)
        return test_result_list

    def request_with_status(self, method, endpoint, *args, **kwargs):
        """
        Issue request and get Json response.

        :param method: 'GET', 'POST', 'HEAD', 'DELETE', 'PUT'
        :param endpoint: e.g. '/application'
        :param args:
        :param kwargs:
        :return:
        """
        r = self.ah.request(method, endpoint, *args, **kwargs)
        r.raise_for_status()
        return r.json()

    def agm_login(self):
        self.ah.login()

    def agm_logout(self):
        self.ah.logout()


class AGMApiTestExecution(object):
    """
    This object represents an execution of testing all the endpoints using get/list, get/detailed, and head calls

    It's data dictionary is structured as:
    {'version': '<agm_version>', 'time': '<execution_datetime>', 'ipaddress': '<ip of agm>', 'tests':
        {
            'list': [<CallTestResponse>, <CallTestResponse>, <CallTestResponse>, ...],
            'detail': [<CallTestResponse>, ...],
            'head': [<CallTestResponse>, ...],
        }
    }
    """
    def __init__(self, ipaddress, username, password, iterations=10):
        self.version = ''
        self.time = ''
        self.tests = {'list': '', 'detail': '', 'head': ''}
        self.ipaddress = ipaddress
        self.iterations = iterations
        self.api_tester = APICallTester(ipaddress, username, password)

    def run(self):
        self.api_tester.agm_login()
        self.version = self.get_version()
        self.time = self.get_time()
        # run list, detail and head calls for all endpoints
        self.tests['list'] = [o._data for o in self.api_tester.time_calls(ENDPOINTS, self.iterations)]
        self.tests['detail'] = [o._data for o in self.api_tester.time_detail_calls(ENDPOINTS, self.iterations)]
        self.tests['head'] = [o._data for o in self.api_tester.time_head_calls(ENDPOINTS, self.iterations)]
        self._append_to_json()

    def _append_to_json(self):
        self._create_json_if_not_exist()
        with open(JSON_FILENAME, 'r') as f:
            json_data = json.load(f)
        json_data.append(self.data)
        with open(JSON_FILENAME, 'w') as f:
            json.dump(json_data, f)

    def _create_json_if_not_exist(self):
        if not os.path.exists(JSON_FILENAME):
            with open(JSON_FILENAME, 'w') as f:
                json.dump(list(), f)

    def print_json_data(self):
        with open(JSON_FILENAME) as f:
            pprint.pprint(json.load(f))

    def get_version(self):
        return '8.1.0.1482'
        # return self.api_tester.request_with_status('GET', '/configuration')

    def get_time(self):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))

    @property
    def data(self):
        return {'time': self.time, 'version': self.version, 'ipaddress': self.ipaddress, 'iterations': self.iterations,
                'tests': self.tests}


class CallTestResponse(object):
    """
    This object represents the result of an API call test against a certain endpoint.

    Example:
    Given that we test an endpoint (e.g. '/application') 10 times, and the average time between
    those 10 calls was 3 seconds, and each of the calls returned 88 applications, this
    CallTestResponse object would have the following attributes:

    self.endpoint == '/application'
    self.iterations == 10
    self.times = ['1.0', '1.1', '1.2', ...] # seconds
    self.count == 88
    self.source_ip
    self.version = '7.1.0.132'

    """
    # Should be a named tuple, but keeping python 2.6 compatibility
    def __init__(self, agm_lib, endpoint, iterations=10):
        """
        :param AGMLib object, with active rest connection
        :param endpoint: e.g. '/application'
        :param iterations: amount of times to iterate a call to get average time
        """
        self.agm_lib = agm_lib
        self.source_ip = agm_lib.ah.host

        epoch_time = time.time()
        self.date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch_time))

        self.endpoint = endpoint
        self.iterations = iterations
        self.version = ''
        self.times = list()
        self.count = None

    def run_list(self):
        """ Runs GET list api call of given number of iterations """
        self.times = self._test_api_call(self.endpoint, self.iterations)
        __, r = self._time_call(self.endpoint)
        self.count = r['count']

    def run_detail(self):
        """ Runs GET detail api call of given number of iterations """
        self.times = self._test_api_call_detailed(self.endpoint, self.iterations)
        _, r = self._time_call(self.endpoint)
        self.count = r['count']

    def run_head(self):
        self.times = self._test_api_head_call(self.endpoint, self.iterations)
        self.count = 1

    def _test_api_call(self, endpoint, iterations=10, *args, **kwargs):
        """ Repeat call N times, and get the avg, min, and max time that the call takes for response """
        times = list()
        for i in range(0, iterations):
            elapased_time, __ = self._time_call(endpoint, *args, **kwargs)
            times.append(elapased_time)
        return times

    def _test_api_head_call(self, endpoint, iterations=10, *args, **kwargs):
        times = list()
        for i in range(0, iterations):
            elapased_time, __ = self._time_head_call(endpoint, *args, **kwargs)
            times.append(elapased_time)
        return times

    def _test_api_call_detailed(self, endpoint, iterations=10, *args, **kwargs):
        # Get id from first element of endpoint
        r = self.agm_lib.request_with_status('GET', endpoint, *args, **kwargs)
        try:
            href = r['items'][0]['href']
            call = '/' + href.split('/actifio/')[1]
        except IndexError:
            return None, None, None
        # Run detailed call against that id
        print(f'Issuing detail {iterations} calls: GET {call}')
        times = self._test_api_call(f'{call}', iterations, *args, **kwargs)
        print(times)
        return times

    def _time_call(self, endpoint, *args, **kwargs):
        """ Return elapsed time, and response """
        start_time = time.time()
        r = self.agm_lib.request_with_status('GET', endpoint, *args, **kwargs)
        elapsed_time = time.time() - start_time
        return elapsed_time, r

    def _time_head_call(self, endpoint, *args, **kwargs):
        start_time = time.time()
        r = self.agm_lib.ah.head(endpoint)
        elapsed_time = time.time() - start_time
        return elapsed_time, r

    @property
    def _data(self):
        return {'endpoint': self.endpoint, 'count': self.count, 'times': self.times}

    def __str__(self):
        return f'Endpoint: {self.endpoint}\nResponse Size: {self.count}\n' \
               f'Times: {self.times}\nIterations: {self.iterations}'

    def __iter__(self):
        for item in [self.date, self.source_ip, self.endpoint, self.count,
                     self.times, self.iterations, self.version]:
            yield item

    def __getitem__(self, item):
        return self._data[item]


if __name__ == '__main__':
    a = AGMApiTestExecution('172.27.6.99', 'admin', 'password')
    a.run()
