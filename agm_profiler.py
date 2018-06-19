from actagm.agm_helper import AgmHelper
import time
import os
import logging

logging.basicConfig(level=logging.INFO)


ENDPOINTS = ('/cluster', '/consistencygroup', '/logicalgroup', '/jobstatus', '/application',
             '/slt', '/slp', '/host', '/user', '/role', '/org', '/diskpool', '/backup')

ENDPOINTS_DETAIL = ('/cluster', '/consistencygroup', '/logicalgroup', '/jobstatus', '/application',
                    '/slt', '/slp', '/host', '/user', '/role', '/org', '/diskpool', '/backup')


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
            call_test_response.run()
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


class CallTestResponse(object):
    """
    This object represents the result of an API call test against a certain endpoint.

    Example:
    Given that we test an endpoint (e.g. '/application') 10 times, and the average time between
    those 10 calls was 3 seconds, and each of the calls returned 88 applications, this
    CallTestResponse object would have the following attributes:

    self.endpoint == '/application'
    self.iterations == 10
    self.avg_time == 3.0
    self.max_time == 3.4
    self.min_time == 2.8
    self.count == 88
    self.source_ip

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
        self.avg_time = self.min_time = self.max_time = self.count = None

    def run(self):
        """ Runs GET list api call of given number of iterations """
        self.avg_time, self.min_time, self.max_time = self._test_api_call(self.endpoint, self.iterations)
        __, r = self._time_call(self.endpoint)
        self.count = r['count']

    def run_detail(self):
        """ Runs GET detail api call of given number of iterations """
        self.avg_time, self.min_time, self.max_time = self._test_api_call_detailed(self.endpoint, self.iterations)
        _, r = self._time_call(self.endpoint)
        self.count = r['count']

    def run_head(self):
        self.avg_time, self.min_time, self.max_time = self._test_api_head_call(self.endpoint, self.iterations)
        # self._time_head_call(self.endpoint)
        self.count = 1

    def _test_api_call(self, endpoint, iterations=10, *args, **kwargs):
        """ Repeat call N times, and get the avg, min, and max time that the call takes for response """
        times = []
        for i in range(2, iterations):
            elapased_time, __ = self._time_call(endpoint, *args, **kwargs)
            times.append(elapased_time)
        avg_time = float(sum(times)) / max(len(times), 1)
        min_time = min(times)
        max_time = max(times)
        return avg_time, min_time, max_time

    def _test_api_head_call(self, endpoint, iterations=10, *args, **kwargs):
        times = []
        for i in range(2, iterations):
            elapased_time, __ = self._time_head_call(endpoint, *args, **kwargs)
            times.append(elapased_time)
        avg_time = float(sum(times)) / max(len(times), 1)
        min_time = min(times)
        max_time = max(times)
        return avg_time, min_time, max_time

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
        avg_time, min_time, max_time = self._test_api_call(f'{call}', iterations, *args, **kwargs)
        print(f'avg_time: {avg_time}, min_time: {min_time}, max_time: {max_time}')
        return avg_time, min_time, max_time

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
        return {'date': self.date, 'source_ip': self.source_ip, 'endpoint': self.endpoint, 'count': self.count,
                'avg_time': self.avg_time, 'min_time': self.min_time, 'max_time': self.max_time,
                'iterations': self.iterations}

    def __str__(self):
        return 'Endpoint: {0}\nResponse Size:{5}\nAvg_time: {1}\nMin_time: {2}\nMax_time: {3}\nIterations: {4}'.format(
            self.endpoint, self.avg_time, self.min_time, self.max_time, self.iterations, self.count)

    def __iter__(self):
        for item in [self.date, self.source_ip, self.endpoint, self.count,
                     self.avg_time, self.min_time, self.max_time, self.iterations]:
            yield item

    def __getitem__(self, item):
        return self._data[item]


def single_row_format(results_obj_li):
    header = ['date', 'iterations']
    single_row = list()
    # time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(1347517370))
    single_row += [results_obj_li[0].date]
    single_row += [results_obj_li[0].iterations]
    for endpoint in results_obj_li:
        header += [f'{endpoint.endpoint} count']
        single_row += [endpoint.count]
        header += [f'{endpoint.endpoint} avg_time']
        single_row += [endpoint.avg_time]
        header += [f'{endpoint.endpoint} min_time']
        single_row += [endpoint.min_time]
        header += [f'{endpoint.endpoint} max_time']
        single_row += [endpoint.max_time]
    return header, single_row


def export_csv(header, row):
    with open('results_csv.csv', 'w') as f:
        f.write(','.join([str(item) for item in header]))
        f.write('\n')
        f.write(','.join([str(item) for item in row]))
        f.write('\n')


if __name__ == '__main__':
    # a = APICallTester('172.17.139.215', 'admin', 'password')
    # a.agm_login()
    # result_obj_li = a.time_detail_calls(ENDPOINTS_DETAIL)
    # print(result_obj_li)
    # header, single_row = single_row_format(result_obj_li)
    # export_csv(header, single_row)

    a = APICallTester('172.17.139.215', 'admin', 'password')
    a.agm_login()
    result_obj_li = a.time_head_calls(ENDPOINTS_DETAIL)
    print(result_obj_li)
    print(result_obj_li[0]._data)
