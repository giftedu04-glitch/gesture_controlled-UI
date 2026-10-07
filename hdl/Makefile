# cocotb + Icarus Verilog entry point for the HDL tests.
#
#   make               run all tests (default simulator: icarus)
#   make SIM=verilator run with another simulator if you have one installed
#   make clean         remove build artefacts
#
# On Windows run `make test` from a shell where `python` is your
# project virtualenv (see README "HDL tests"), or call the script
# directly: .venv\Scripts\python hdl\test_gesture_controller.py

PYTHON ?= python
SIM ?= icarus

.PHONY: test clean
test:
	$(PYTHON) test_gesture_controller.py $(SIM)

clean:
	rm -rf sim_build results.xml
