try:
    from setuptools import setup, Extension
except ImportError:
    from distutils.core import setup, Extension
import sys
from distutils.command.build_ext import build_ext
from distutils.errors import DistutilsPlatformError, CCompilerError

class optional_build_ext(build_ext):
    # This class allows C extension building to fail.
    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            self._unavailable()

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except CCompilerError, x:
            self._unavailable()

    def _unavailable(self):
        print '*' * 78
        print """
WARNING: Could not compile C extension, contextual help will not be available.
"""
        print '*' * 78


ext_modules = []
install_requires = []

if 'win' in sys.platform:
    ext_modules = []
    install_requires = ['pyreadline']
    if sys.version_info[:2] < (2, 5):
        install_requires.append('ctypes')
else:
    ext_modules = [Extension('cly._rlext', ['cly/_rlext.c'],
                             libraries=['readline', 'curses'])]

setup(
    name='cly',
    url='http://swapoff.org/cly',
    download_url='http://swapoff.org/cly',
    author='Alec Thomas',
    author_email='alec@swapoff.org',
    version='1.0',
    description='A module for adding powerful text-based consoles to your application.',
    long_description=\
"""CLY is a Python module for simplifying the creation of interactive shells.
Kind of like the builtin "cmd" module on steroids.""",
    license='BSD',
    platforms=['any'],
    packages=['cly'],
    zip_safe=False,
    test_suite='cly.test.suite',
    classifiers=['Development Status :: 3 - Alpha',
                 'Intended Audience :: Developers',
                 'License :: OSI Approved :: BSD License',
                 'Operating System :: OS Independent',
                 'Topic :: System :: Shells',
                 'Environment :: Console',
                 'Topic :: Software Development :: Libraries'],
    ext_modules=ext_modules,
    install_requires=install_requires,
    cmdclass={'build_ext': optional_build_ext},
    )
