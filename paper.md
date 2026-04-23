---
title: 'stataudit: A Python tool for automated statistical reporting audits in machine learning papers'
tags:
  - Python
  - statistics
  - reproducibility
  - machine-learning
  - auditing
authors:
  - name: Vaibhav Deshmukh
    orcid: 0000-0001-6745-7062
    affiliation: 1
affiliations:
  - name: Independent Researcher, Nagpur, India
    index: 1
date: 23 April 2026
bibliography: paper.bib
---

# Summary

`stataudit` is a Python command-line tool that parses machine learning paper PDFs and LaTeX sources to automatically detect common statistical reporting errors and omissions: missing confidence intervals, unreported variance across seeds, inappropriate significance tests, missing effect sizes, and p-value inconsistencies. It extracts numerical claims from text and tables using a combination of rule-based parsing and regular expressions, then applies a configurable checklist of auditing rules drawn from best-practice guidelines for empirical ML research [@pineau2021improving].

# Statement of Need

Statistical reporting quality in machine learning papers has been widely criticised [@gundersen2018state]. Common problems include reporting only mean performance without variance, comparing systems without statistical tests, and selecting random seeds post-hoc. Manual auditing of papers for these issues is labour-intensive and inconsistently applied. `stataudit` automates a first-pass audit that flags potential reporting issues with line-level citations back to the source document, enabling authors to self-check before submission, reviewers to verify claims efficiently, and meta-researchers to study reporting quality at scale [@stodden2016enhancing].

# Acknowledgements

The author used Claude (Anthropic) for drafting portions of this manuscript. All scientific claims and design decisions are the author's own.

# References
