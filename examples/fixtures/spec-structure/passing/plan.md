# Implementation Plan: Widget Export

Add a CSV serializer behind the existing export endpoint; stream rows so
large lists do not load fully into memory.
