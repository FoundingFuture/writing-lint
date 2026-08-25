---
title: Build pipeline stages
description: The four stages the build runs, the inputs each stage reads, and the exit codes it returns.
date: 2026-02-11
---

## Stage order

Compilation happens before any check reads the output. The compiler writes
to a staging directory, so the published tree stays untouched.

Four stages run in a fixed order. Each stage stops the run on its first
failure. The exit code names the stage that failed.

## Inputs

Every stage reads the source tree. The rendered output is a derived
artefact. A minified selector gives a warning no name to quote back.

The stylesheet checker is the exception, and it reads both trees.

## Exit codes

A run returns 0 when no stage reported anything. A finding returns 1. A
malformed command line returns 2. An absent tool returns 3.

Three of the four stages need no tool beyond the compiler. The validity
stage needs two tools. An absent tool fails the run under continuous
integration and warns on a workstation.
