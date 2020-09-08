#!/usr/bin/env python3

# Copyright © 2018 Red Hat Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author: Geetika Batra <gbatra@redhat.com>
#

"""Project setup file for fabric8 analytics stacks report project."""

from setuptools import setup, find_packages


def get_requirements():
    """
    Parse dependencies from 'requirements.in' file.

    Collecting dependencies from 'requirements.in' as a list,
    this list will be used by 'install_requires' to specify minimal dependencies
    needed to run the application.
    """
    with open('requirements.in') as fd:
        return fd.read().splitlines()


install_requires = get_requirements()

# pip doesn't install from dependency links by default,
# so one should install dependencies by
#  `pip install -r requirements.txt`, not by `pip install .`
#  See https://github.com/pypa/pip/issues/2023

setup(
    name='f8a-stacks-report-scheduler',
    version='0.1',
    scripts=[
    ],
    packages=find_packages(exclude=['tests', 'tests.*']),
    install_requires=install_requires,
    include_package_data=True,
    author='Geetika Batra',
    author_email='gbatra@redhat.com',
    description='stacks report scheduler for fabric8 analytics',
    license='ASL 2.0',
    keywords='f8a-stacks-report-scheduler',
    url=('https://github.com/fabric8-analytics/'
         'f8a-stacks-report-scheduler')
)
