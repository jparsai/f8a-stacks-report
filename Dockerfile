FROM registry.centos.org/centos/centos:7
  
ENV APP_DIR='/f8a_report' \
    F8A_UTIL_VERSION=e220735

WORKDIR ${APP_DIR}

RUN yum install -y epel-release &&\
    yum install -y gcc git python36-pip python36-devel &&\
    yum clean all &&\
    mkdir -p ${APP_DIR}

RUN pip3 install --upgrade pip
RUN pip3 install git+https://github.com/fabric8-analytics/fabric8-analytics-utils.git@${F8A_UTIL_VERSION}
RUN pip3 install git+https://git@github.com/fabric8-analytics/fabric8-analytics-version-comparator.git#egg=f8a_version_comparator

COPY f8a_report/ ${APP_DIR}/f8a_report
COPY requirements.txt ${APP_DIR}
RUN pip3 install -r requirements.txt
CMD ["f8a_report/stack_report_main.py"]
ENTRYPOINT ["python3"]

