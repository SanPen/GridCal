Troubleshooting
=================================

This section includes known issues and their solutions.

Clean crashes on ARM-based MacOS
-----------------------------------

You may find GridCal crashing without any explanation on MacOS. A reason we've found is that the standard Numpy
package is compiled against OpenBlas and not Apple's native Accelerate framework for linear algebra.
To fix this, you'll need to compile numpy from source:

- uninstall your numpy: `[python folder]/python -m pip uninstall numpy`
- install from source: `[python folder]/python -m pip install -U --no-binary :all: numpy`

You may need to install `xcode` for this to work

Here `[python folder]/python` is the complete path to the python binary executable file that you're using to run GridCal.
