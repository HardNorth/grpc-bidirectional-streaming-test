from subprocess import check_call

from setuptools import setup, find_packages
from setuptools.command.develop import develop
from setuptools.command.install import install

GRPC_GENERATION_SCRIPT = "python -m grpc_tools.protoc -I./proto " \
                         "--python_out=./reportportal_grpc_client " \
                         "--grpc_python_out=./reportportal_grpc_client/grpc " \
                         "./proto/reportportal.proto"


class PreDevelopCommand(develop):
    """Pre-installation for development mode."""

    def run(self):
        check_call(GRPC_GENERATION_SCRIPT.split())
        develop.run(self)


class PreInstallCommand(install):
    """Pre-installation for installation mode."""

    def run(self):
        check_call(GRPC_GENERATION_SCRIPT.split())
        install.run(self)


__version__ = '0.0.1'

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='reportportal-grpc-client',
    packages=find_packages(exclude=('tests', 'tests.*')),
    version=__version__,
    description='Test gRPC Python client for Report Portal',
    author_email='vadzim_hushchanskou@epam.com',
    url='https://github.com/reportportal/client-Python',
    download_url=('https://github.com/reportportal/client-Python/'
                  'tarball/%s' % __version__),
    license='Apache 2.0',
    keywords=['testing', 'reporting', 'reportportal'],
    classifiers=[
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10'
    ],
    install_requires=requirements
)
