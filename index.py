#!/usr/bin/python
# -*- coding: utf-8 -*-
# Generate indexes files for the Crep's chordbook compilation. This is
# a replacement for the original makeindex program written in C that
# produces an index file (.sbx) from a file generated by the latex
# compilation of the songbook (.sxd).
#
# Usage : songbook-makeindex.py src
#         src is the .sxd file generated by latex
#

from unidecode import unidecode
import sys
import re
import locale
import warnings

from tools import processauthors
from utils.plastex import simpleparse

# Pattern set to ignore latex command in title prefix
keywordPattern = re.compile(r"^%(\w+)\s?(.*)$")
firstLetterPattern = re.compile(r"^(?:\{?\\\w+\}?)*[^\w]*(\w)")

def sortkey(value):
    '''
    From a title, return something usable for sorting. It handles locale (but
    don't forget to call locale.setlocale(locale.LC_ALL, '')). It also handles
    the sort with  latex escape sequences.
    '''
    return locale.strxfrm(unidecode(simpleparse(value).replace(' ', 'A')))

def processSXDEntry(tab):
    return (tab[0], tab[1], tab[2])

def processSXD(filename):
    file = open(filename)
    data = []
    for line in file:
        data.append(line.strip())
    file.close()

    i = 1
    idx = index(data[0])

    if len(data) > 1:
        while data[i].startswith('%'):
            keywords = keywordPattern.match(data[i]).groups()
            idx.keyword(keywords[0],keywords[1])
            i += 1

    idx.compileKeywords()
    for i in range(i,len(data),3):
        entry = processSXDEntry(data[i:i+3])
        idx.add(entry[0],entry[1],entry[2])

    return idx

class index:
    def __init__(self, indextype):
        self.data = dict()
        self.keywords = dict()
        if indextype == "TITLE INDEX DATA FILE":
            self.indextype = "TITLE"
        elif indextype == "SCRIPTURE INDEX DATA FILE":
            self.indextype = "SCRIPTURE"
        elif indextype == "AUTHOR INDEX DATA FILE":
            self.indextype = "AUTHOR"
        else:
            self.indextype = ""

    def filter(self, key):
        letter = firstLetterPattern.match(key).group(1)
        if re.match('\d',letter):
            letter = '0-9'
        return (letter.upper(), key)

    def keyword(self, key, word):
        if not self.keywords.has_key(key):
            self.keywords[key] = []
        self.keywords[key].append(word)

    def compileKeywords(self):
        self.prefix_patterns = []
        if self.indextype == "TITLE":
            if 'prefix' in self.keywords:
                for prefix in self.keywords['prefix']:
                    self.prefix_patterns.append(re.compile(r"^(%s)(\b|\\)(\s*.*)$" % prefix))

        self.authwords = {"after": [], "ignore": [], "sep": []}
        if self.indextype == "AUTHOR":
            for key in self.keywords:
                if key in self.authwords:
                    self.authwords[key] = self.keywords[key]
            for word in self.authwords.keys():
                if word in self.keywords:
                    if word == "after":
                        self.authwords[word] = [re.compile(r"^.*%s\b(.*)" % after) for after in self.keywords[word]]
                    elif word == "sep":
                        self.authwords[word] = [" %s" % sep for sep in self.authwords[word]] + [","]
                        self.authwords[word] = [re.compile(r"^(.*)%s (.*)$" % sep) for sep in self.authwords[word] ]
                    else:
                        self.authwords[word] = self.keywords[word]

    def _raw_add(self, key, number, link):
        (first, key) = self.filter(key)
        if not self.data.has_key(first):
            self.data[first] = dict()
        if not self.data[first].has_key(key):
            self.data[first][key] = []
        self.data[first][key].append({'num':number, 'link':link})

    def add(self, key, number, link):
        if self.indextype == "TITLE":
            # Removing prefixes before titles
            for pattern in self.prefix_patterns:
                match = pattern.match(key)
                if match:
                    self._raw_add(
                            "%s (%s)" % (match.group(2) + match.group(3), match.group(1)),
                            number, link)
                    return
            self._raw_add(key, number, link)

        if self.indextype == "AUTHOR":
            # Processing authors
            for author in processauthors(
                    key,
                    **self.authwords):
                self._raw_add(author, number, link)

    def refToStr(self, ref):
        if sys.version_info >= (2,6):
            return '\\hyperlink{{{0[link]}}}{{{0[num]}}}'.format(ref)
        else:
            return '\\hyperlink{%(link)s}{%(num)s}' % ref

    def entryToStr(self, key, entry):
        if sys.version_info >= (2,6):
            return unicode('\\idxentry{{{0}}}{{{1}}}\n').format(key, '\\\\'.join(map(self.refToStr, entry)))
        else:
            return unicode('\\idxentry{%s}{%s}\n') % (key, '\\\\'.join(map(self.refToStr, entry)))

    def idxBlockToStr(self, letter, entries):
        str = '\\begin{idxblock}{'+letter+'}'+'\n'
        for key in sorted(entries.keys(), key=sortkey):
            str += self.entryToStr(key, entries[key])
        str += '\\end{idxblock}'+'\n'
        return str

    def entriesToStr(self):
        str = ""
        for letter in sorted(self.data.keys()):
            str += self.idxBlockToStr(letter, self.data[letter])
        return str