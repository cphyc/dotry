# IMPORTANT

This program is not stable enough for a daily use! Use at your own risk.
Moreover the following guide may not be up-to-date.


# Dotry

Have you ever had to rerun a whole set of simulation because you couldn't remember if a given file was up to date with a function? Dotry stands for *Do*n't *Tr*ust *Y*ourself but your computer…
This tool aims at preventing such an issue by introducing the concept of `TaskManager`. Whenever you create a task manager, you can register function into it. These functions will automagically be parsed to find the input/output files, register them in the manager. Each time you run one of the register function, the task manager will run all the functions required to provide an up-to-date input it.

Moreover the task manager stores all the file in a `data` directory (which you can customize).

## How to use?
Imagine you have two functions:

    import numpy as np
    def A():
	    data_in = np.random.rand(10, 10)
		data_out = data_in**2

		np.save('output_A.dat', data_out)

	def B():
	    data_in = np.load('output_A')
		data_out = data_in - 10
		np.save('output_B.dat', data_out)

For much longer functions, it is easy to forget about which file is up-to-date with each function. To solve this issue, you can wrap your function using a task manager, so that all the outputs files are up-to-date with all the inputs and the function's definitions. First, create a task manager instance:

    import numpy as np
	import scyframework as sf
	tm = sf.TaskManager()

then, modify you functions so that the task manager can handle them

	@tm.register
    def A():
	    data_in = np.random.rand(10, 10)
		data_out = data_in**2

		np.save('output_A.dat', data_out)

	@tm.register
	def B():
	    data_in = np.load('output_A.dat')
		data_out = data_in - 10
		np.save('output_B.dat')

We're almost there, you then need to wrap all the input/output statements using `tm.din` (inputs) and `tm.dout` (outputs) to finally have

    import numpy as np
	import scyframework as sf
	tm = sf.TaskManager()

	@tm.register
    def A():
		np.random.seed(1234)
	    data_in = np.random.rand(10, 10)
		data_out = data_in**2
		np.save(tm.dout('output_A.dat'), data_out)

	@tm.register
	def B():
	    data_in = np.load(tm.din('output_A.dat'))
		data_out = data_in - 10
		np.save(tm.dout('output_B.dat'), data_out)

The `tm.din` and `tm.dout` statements have two roles. First, it converts the filename to a full path so that your data isn't messing up with your local folder.
For example here:

	 > print(tm.din('output_B.dat'))
	 /path/to/current/folder/data/output_B

Then it helps the taskmanager to discover your inputs/outputs so that it knows which functions provides which data. Now if you run the file
