# Copyright 2015-2017 Espressif Systems (Shanghai) PTE LTD
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import functools
import os
import re

from tiny_test_fw import TinyFW, Utility
from .IDFApp import IDFApp, Example, LoadableElfTestApp, UT, TestApp  # noqa: export all Apps for users
from .IDFDUT import IDFDUT, ESP32DUT, ESP32S2DUT, ESP8266DUT, ESP32QEMUDUT  # noqa: export DUTs for users
from .DebugUtils import OCDProcess, GDBProcess, TelnetProcess, CustomProcess  # noqa: export DebugUtils for users

# pass TARGET_DUT_CLS_DICT to Env.py to avoid circular dependency issue.
TARGET_DUT_CLS_DICT = {
    'ESP32': ESP32DUT,
    'ESP32S2': ESP32S2DUT,
}


def format_case_id(chip, case_name):
    return "{}.{}".format(chip, case_name)


try:
    string_type = basestring
except NameError:
    string_type = str


def upper_list(text):
    if not text:
        return text
    if isinstance(text, string_type):
        res = text.upper()
    else:
        res = [item.upper() for item in text]
    return res


def ci_target_check(func):
    @functools.wraps(func)
    def wrapper(**kwargs):
        target = upper_list(kwargs.get('target', []))
        ci_target = upper_list(kwargs.get('ci_target', []))
        if not set(ci_target).issubset(set(target)):
            raise ValueError('ci_target must be a subset of target')

        return func(**kwargs)

    return wrapper


@ci_target_check
def idf_example_test(app=Example, target="ESP32", ci_target=None, module="examples", execution_time=1,
                     level="example", erase_nvs=True, config_name=None, **kwargs):
    """
    decorator for testing idf examples (with default values for some keyword args).

    :param app: test application class
    :param target: target supported, string or list
    :param ci_target: target auto run in CI, if None than all target will be tested, None, string or list
    :param module: module, string
    :param execution_time: execution time in minutes, int
    :param level: test level, could be used to filter test cases, string
    :param erase_nvs: if need to erase_nvs in DUT.start_app()
    :param config_name: if specified, name of the app configuration
    :param kwargs: other keyword args
    :return: test method
    """

    def test(func):
        original_method = TinyFW.test_method(app=app, target=upper_list(target), ci_target=upper_list(ci_target), module=module,
                                             execution_time=execution_time, level=level, dut_dict=TARGET_DUT_CLS_DICT,
                                             erase_nvs=erase_nvs, **kwargs)
        test_func = original_method(func)
        test_func.case_info["ID"] = format_case_id(target, test_func.case_info["name"])
        return test_func

    return test


@ci_target_check
def idf_unit_test(app=UT, target="ESP32", ci_target=None, module="unit-test", execution_time=1,
                  level="unit", erase_nvs=True, **kwargs):
    """
    decorator for testing idf unit tests (with default values for some keyword args).

    :param app: test application class
    :param target: target supported, string or list
    :param ci_target: target auto run in CI, if None than all target will be tested, None, string or list
    :param module: module, string
    :param execution_time: execution time in minutes, int
    :param level: test level, could be used to filter test cases, string
    :param erase_nvs: if need to erase_nvs in DUT.start_app()
    :param kwargs: other keyword args
    :return: test method
    """

    def test(func):
        original_method = TinyFW.test_method(app=app, target=upper_list(target), ci_target=upper_list(ci_target), module=module,
                                             execution_time=execution_time, level=level, dut_dict=TARGET_DUT_CLS_DICT,
                                             erase_nvs=erase_nvs, **kwargs)
        test_func = original_method(func)
        test_func.case_info["ID"] = format_case_id(target, test_func.case_info["name"])
        return test_func

    return test


@ci_target_check
def idf_custom_test(app=TestApp, target="ESP32", ci_target=None, module="misc", execution_time=1,
                    level="integration", erase_nvs=True, config_name=None, group="test-apps", **kwargs):
    """
    decorator for idf custom tests (with default values for some keyword args).

    :param app: test application class
    :param target: target supported, string or list
    :param ci_target: target auto run in CI, if None than all target will be tested, None, string or list
    :param module: module, string
    :param execution_time: execution time in minutes, int
    :param level: test level, could be used to filter test cases, string
    :param erase_nvs: if need to erase_nvs in DUT.start_app()
    :param config_name: if specified, name of the app configuration
    :param group: identifier to group custom tests (unused for now, defaults to "test-apps")
    :param kwargs: other keyword args
    :return: test method
    """

    def test(func):
        original_method = TinyFW.test_method(app=app, target=upper_list(target), ci_target=upper_list(ci_target), module=module,
                                             execution_time=execution_time, level=level, dut_dict=TARGET_DUT_CLS_DICT,
                                             erase_nvs=erase_nvs, **kwargs)
        test_func = original_method(func)
        test_func.case_info["ID"] = format_case_id(target, test_func.case_info["name"])
        return test_func

    return test


def log_performance(item, value):
    """
    do print performance with pre-defined format to console

    :param item: performance item name
    :param value: performance value
    """
    performance_msg = "[Performance][{}]: {}".format(item, value)
    Utility.console_log(performance_msg, "orange")
    # update to junit test report
    current_junit_case = TinyFW.JunitReport.get_current_test_case()
    current_junit_case.stdout += performance_msg + "\r\n"


def check_performance(item, value, target):
    """
    check if idf performance meet pass standard

    :param item: performance item name
    :param value: performance item value
    :param target: target chip
    :raise: AssertionError: if check fails
    """

    def _find_perf_item(path):
        with open(path, 'r') as f:
            data = f.read()
        match = re.search(r'#define\s+IDF_PERFORMANCE_(MIN|MAX)_{}\s+([\d.]+)'.format(item.upper()), data)
        return match.group(1), float(match.group(2))

    def _check_perf(op, standard_value):
        if op == 'MAX':
            ret = value <= standard_value
        else:
            ret = value >= standard_value
        if not ret:
            raise AssertionError("[Performance] {} value is {}, doesn't meet pass standard {}"
                                 .format(item, value, standard_value))

    path_prefix = os.path.join(IDFApp.get_sdk_path(), 'components', 'idf_test', 'include')
    performance_files = (os.path.join(path_prefix, target, 'idf_performance_target.h'),
                         os.path.join(path_prefix, 'idf_performance.h'))

    for performance_file in performance_files:
        try:
            op, value = _find_perf_item(performance_file)
        except (IOError, AttributeError):
            # performance file doesn't exist or match is not found in it
            continue

        _check_perf(op, value)
        # if no exception was thrown then the performance is met and no need to continue
        break
