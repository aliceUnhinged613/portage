# config.py -- Portage Config
# Copyright 2007 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Id$

import os

class LoaderError(Exception):
	
	def __init__(self, resource, error_msg):
		"""
		@param resource: Resource that failed to load (file/sql/etc)
		@type resource: String
		@param error_msg: Error from underlying Loader system
		@type error_msg: String
		"""

		self.resource = resource
		self.error_msg = error_msg
	
	def __str__(self):
		return "Failed while loading resource: %s, error was: %s" % (
			self.resource, self.error_msg)


def RecursiveFileLoader(filename):
	"""
	If filename is of type file, return a generate that yields filename
	else if filename is of type directory, return a generator that fields
	files in that directory.
	
	Ignore files beginning with . or ending in ~.
	Prune CVS directories.

	@param filename: name of a file/directory to traverse
	@rtype: list
	@returns: List of files to process
	"""

	if os.path.isdir(filename):
		for root, dirs, files in os.walk(filename):
			if 'CVS' in dirs:
				dirs.remove('CVS')
			files = filter(files, str.startswith('.'))
			files = filter(files, str.endswith('~'))
			for f in files:
				yield f
	else:
		yield filename


class DataLoader(object):

	def __init__(self, validator):
		f = validator
		if f is None:
			# if they pass in no validator, just make a fake one
			# that always returns true
			def validate(key):
				return True
			f = validate
		self._validate = f

	def load(self):
		"""
		Function to do the actual work of a Loader
		"""
		raise NotImplementedError("Please override in a subclass")

class EnvLoader(DataLoader):
	""" Class to access data in the environment """
	def __init__(self, validator):
		DataLoader.__init__(self, validator)

	def load(self):
		return os.environ

class TestTextLoader(DataLoader):
	""" You give it some data, it 'loads' it for you, no filesystem access
	"""
	def __init__(self, validator):
		DataLoader.__init__(self, validator)
		self.data = {}
		self.errors = {}

	def setData(self, text):
		"""Explicitly set the data field
		Args:
			text - a dict of data typical of Loaders
		Returns:
			None
		"""
		if isinstance(text, dict):
			self.data = text
		else:
			raise ValueError("setData requires a dict argument")

	def setErrors(self, errors):
		self.errors = errors
	
	def load(self):
		return (self.data, self.errors)


class FileLoader(DataLoader):
	""" Class to access data in files """

	def __init__(self, filename, validator):
		"""
			Args:
				filename : Name of file or directory to open
				validator : class with validate() method to validate data.
		"""
		DataLoader.__init__(self, validator)
		self.fname = filename

	def load(self):
		"""
		Return the {source: {key: value}} pairs from a file
		Return the {source: [list of errors] from a load

		@param recursive: If set and self.fname is a directory; 
			load all files in self.fname
		@type: Boolean
		@rtype: tuple
		@returns:
		Returns (data,errors), both may be empty dicts or populated.
		"""
		data = {}
		errors = {}
		# I tried to save a nasty lookup on lineparser by doing the lookup
		# once, which may be expensive due to digging in child classes.
		func = self.lineParser
		for fn in RecursiveFileLoader(self.fname):
			f = open(fn, 'rb')
			for line_num, line in enumerate(f):
				func(line, line_num, data, errors)
		return (data, errors)

	def lineParser(self, line, line_num, data, errors):
		""" This function parses 1 line at a time
			Args:
				line: a string representing 1 line of a file
				line_num: an integer representing what line we are processing
				data: a dict that contains the data we have extracted from the file
				      already
				errors: a dict representing parse errors.
			Returns:
				Nothing (None).  Writes to data and errors
		"""
		raise NotImplementedError("Please over-ride this in a child class")

class ItemFileLoader(FileLoader):
	"""
	Class to load data from a file full of items one per line
	
	>>> item1
	>>> item2
	>>> item3
	>>> item1
	
	becomes { 'item1':None, 'item2':None, 'item3':None }
	Note that due to the data store being a dict, duplicates
	are removed.
	"""

	def __init__(self, filename, validator):
		FileLoader.__init__(self, filename, validator)
	
	def lineParser(self, line, line_num, data, errors):
		line = line.strip()
		if line.startswith('#'): # Skip commented lines
			return
		if not len(line): # skip empty lines
			return
		split = line.split()
		if not len(split):
			errors.setdefault(self.fname, []).append(
				"Malformed data at line: %s, data: %s"
				% (line_num + 1, line))
			return
		key = split[0]
		if not self._validate(key):
			errors.setdefault(self.fname, []).append(
				"Validation failed at line: %s, data %s"
				% (line_num + 1, key))
			return
		data[key] = None

class KeyListFileLoader(FileLoader):
	"""
	Class to load data from a file full of key [list] tuples
	
	>>>>key foo1 foo2 foo3
	becomes
	{'key':['foo1','foo2','foo3']}
	"""

	def __init__(self, filename, validator):
		FileLoader.__init__(self, filename, validator)


	def lineParser(self, line, line_num, data, errors):
		line = line.strip()
		if line.startswith('#'): # Skip commented lines
			return
		if not len(line): # skip empty lines
			return
		split = line.split()
		if len(split) < 2:
			errors.setdefault(self.fname, []).append(
				"Malformed data at line: %s, data: %s"
				% (line_num + 1, line))
			return
		key = split[0]
		value = split[1:]
		if not self._validate(key):
			errors.setdefault(self.fname, []).append(
				"Validation failed at line: %s, data %s"
				% (line_num + 1, key))
			return
		if key in data:
			data[key].append(value)
		else:
			data[key] = value


class KeyValuePairFileLoader(FileLoader):
	"""
	Class to load data from a file full of key=value pairs
	
	>>>>key=value
	>>>>foo=bar
	becomes:
	{'key':'value',
	 'foo':'bar'}
	"""

	def __init__(self, filename, validator):
		FileLoader.__init__(self, filename, validator)


	def lineParser(self, line, line_num, data, errors):
		line = line.strip()
		if line.startswith('#'): # skip commented lines
			return
		if not len(line): # skip empty lines
			return
		split = line.split('=')
		if len(split) < 2:
			errors.setdefault(self.fname, []).append(
				"Malformed data at line: %s, data %s"
				% (line_num + 1, line))
			return
		key = split[0]
		value = split[1:]
		if not key:
			errors.setdefault(self.fname, []).append(
				"Malformed key at line: %s, key %s"
				% (line_num + 1, key))
			return
		if not self._validate(key):
			errors.setdefault(self.fname, []).append(
				"Validation failed at line: %s, data %s"
				% (line_num + 1, key))
			return
		if key in data:
			data[key].append(value)
		else:
			data[key] = value
