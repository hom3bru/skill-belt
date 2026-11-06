# tidy-csv

tidy-csv is a small command-line tool that cleans up CSV files. It is a tool for cleaning CSV files, and it works on the
command line, which means you run it from a terminal. Basically, the idea is that you give it a messy CSV file and it
gives you back a tidy one.

## Install

To install tidy-csv you need Python 3.10 or later. Install it with pip:

    pip install tidy-csv

Once you have Python 3.10 or later, you can install tidy-csv with pip by running `pip install tidy-csv` in your
terminal. After that, tidy-csv is installed and ready to use.

## Usage

    tidy-csv input.csv --out clean.csv

This reads input.csv, trims spaces, drops empty rows and writes clean.csv.
