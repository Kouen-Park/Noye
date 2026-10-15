# Phase 8 complex PDF QA

Synthetic layout check. 한국어와 English, table rows, wrapped code and local image.

## Table / 긴 표

| ID | English | 한국어 | Measure | Condition | Exact token |
| --- | --- | --- | --- | --- | --- |
| T001 | Row 001 | 표 001 보존 | 1 ms | Sunday exception | TOKEN-001-END |
| T002 | Row 002 | 표 002 보존 | 2 ms | Sunday exception | TOKEN-002-END |
| T003 | Row 003 | 표 003 보존 | 3 ms | Sunday exception | TOKEN-003-END |
| T004 | Row 004 | 표 004 보존 | 4 ms | Sunday exception | TOKEN-004-END |
| T005 | Row 005 | 표 005 보존 | 5 ms | Sunday exception | TOKEN-005-END |
| T006 | Row 006 | 표 006 보존 | 6 ms | Sunday exception | TOKEN-006-END |
| T007 | Row 007 | 표 007 보존 | 7 ms | Sunday exception | TOKEN-007-END |
| T008 | Row 008 | 표 008 보존 | 8 ms | Sunday exception | TOKEN-008-END |
| T009 | Row 009 | 표 009 보존 | 9 ms | Sunday exception | TOKEN-009-END |
| T010 | Row 010 | 표 010 보존 | 10 ms | Sunday exception | TOKEN-010-END |
| T011 | Row 011 | 표 011 보존 | 11 ms | Sunday exception | TOKEN-011-END |
| T012 | Row 012 | 표 012 보존 | 12 ms | Sunday exception | TOKEN-012-END |
| T013 | Row 013 | 표 013 보존 | 13 ms | Sunday exception | TOKEN-013-END |
| T014 | Row 014 | 표 014 보존 | 14 ms | Sunday exception | TOKEN-014-END |
| T015 | Row 015 | 표 015 보존 | 15 ms | Sunday exception | TOKEN-015-END |
| T016 | Row 016 | 표 016 보존 | 16 ms | Sunday exception | TOKEN-016-END |
| T017 | Row 017 | 표 017 보존 | 17 ms | Sunday exception | TOKEN-017-END |
| T018 | Row 018 | 표 018 보존 | 18 ms | Sunday exception | TOKEN-018-END |
| T019 | Row 019 | 표 019 보존 | 19 ms | Sunday exception | TOKEN-019-END |
| T020 | Row 020 | 표 020 보존 | 20 ms | Sunday exception | TOKEN-020-END |
| T021 | Row 021 | 표 021 보존 | 21 ms | Sunday exception | TOKEN-021-END |
| T022 | Row 022 | 표 022 보존 | 22 ms | Sunday exception | TOKEN-022-END |
| T023 | Row 023 | 표 023 보존 | 23 ms | Sunday exception | TOKEN-023-END |
| T024 | Row 024 | 표 024 보존 | 24 ms | Sunday exception | TOKEN-024-END |
| T025 | Row 025 | 표 025 보존 | 25 ms | Sunday exception | TOKEN-025-END |
| T026 | Row 026 | 표 026 보존 | 26 ms | Sunday exception | TOKEN-026-END |
| T027 | Row 027 | 표 027 보존 | 27 ms | Sunday exception | TOKEN-027-END |
| T028 | Row 028 | 표 028 보존 | 28 ms | Sunday exception | TOKEN-028-END |
| T029 | Row 029 | 표 029 보존 | 29 ms | Sunday exception | TOKEN-029-END |
| T030 | Row 030 | 표 030 보존 | 30 ms | Sunday exception | TOKEN-030-END |
| T031 | Row 031 | 표 031 보존 | 31 ms | Sunday exception | TOKEN-031-END |
| T032 | Row 032 | 표 032 보존 | 32 ms | Sunday exception | TOKEN-032-END |
| T033 | Row 033 | 표 033 보존 | 33 ms | Sunday exception | TOKEN-033-END |
| T034 | Row 034 | 표 034 보존 | 34 ms | Sunday exception | TOKEN-034-END |
| T035 | Row 035 | 표 035 보존 | 35 ms | Sunday exception | TOKEN-035-END |
| T036 | Row 036 | 표 036 보존 | 36 ms | Sunday exception | TOKEN-036-END |
| T037 | Row 037 | 표 037 보존 | 37 ms | Sunday exception | TOKEN-037-END |
| T038 | Row 038 | 표 038 보존 | 38 ms | Sunday exception | TOKEN-038-END |
| T039 | Row 039 | 표 039 보존 | 39 ms | Sunday exception | TOKEN-039-END |
| T040 | Row 040 | 표 040 보존 | 40 ms | Sunday exception | TOKEN-040-END |

## Code / 긴 코드

```python
row_001 = "코드 001 / exact-001"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C001
row_002 = "코드 002 / exact-002"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C002
row_003 = "코드 003 / exact-003"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C003
row_004 = "코드 004 / exact-004"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C004
row_005 = "코드 005 / exact-005"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C005
row_006 = "코드 006 / exact-006"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C006
row_007 = "코드 007 / exact-007"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C007
row_008 = "코드 008 / exact-008"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C008
row_009 = "코드 009 / exact-009"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C009
row_010 = "코드 010 / exact-010"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C010
row_011 = "코드 011 / exact-011"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C011
row_012 = "코드 012 / exact-012"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C012
row_013 = "코드 013 / exact-013"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C013
row_014 = "코드 014 / exact-014"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C014
row_015 = "코드 015 / exact-015"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C015
row_016 = "코드 016 / exact-016"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C016
row_017 = "코드 017 / exact-017"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C017
row_018 = "코드 018 / exact-018"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C018
row_019 = "코드 019 / exact-019"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C019
row_020 = "코드 020 / exact-020"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C020
row_021 = "코드 021 / exact-021"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C021
row_022 = "코드 022 / exact-022"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C022
row_023 = "코드 023 / exact-023"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C023
row_024 = "코드 024 / exact-024"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C024
row_025 = "코드 025 / exact-025"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C025
row_026 = "코드 026 / exact-026"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C026
row_027 = "코드 027 / exact-027"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C027
row_028 = "코드 028 / exact-028"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C028
row_029 = "코드 029 / exact-029"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C029
row_030 = "코드 030 / exact-030"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C030
row_031 = "코드 031 / exact-031"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C031
row_032 = "코드 032 / exact-032"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C032
row_033 = "코드 033 / exact-033"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C033
row_034 = "코드 034 / exact-034"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C034
row_035 = "코드 035 / exact-035"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C035
row_036 = "코드 036 / exact-036"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C036
row_037 = "코드 037 / exact-037"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C037
row_038 = "코드 038 / exact-038"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C038
row_039 = "코드 039 / exact-039"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C039
row_040 = "코드 040 / exact-040"  # long_identifier_long_identifier_long_identifier_long_identifier_long_identifier_END-C040
```

## Image / 로컬 이미지

![Bundled local file icon](/file.svg)

Image caption: bundled asset, no external download. 로컬 파일 아이콘.

## Lists and quotation

- L001: 한국어·English exact list value 1.
- L002: 한국어·English exact list value 2.
- L003: 한국어·English exact list value 3.
- L004: 한국어·English exact list value 4.
- L005: 한국어·English exact list value 5.
- L006: 한국어·English exact list value 6.
- L007: 한국어·English exact list value 7.
- L008: 한국어·English exact list value 8.
- L009: 한국어·English exact list value 9.
- L010: 한국어·English exact list value 10.
- L011: 한국어·English exact list value 11.
- L012: 한국어·English exact list value 12.
- L013: 한국어·English exact list value 13.
- L014: 한국어·English exact list value 14.
- L015: 한국어·English exact list value 15.
- L016: 한국어·English exact list value 16.

> Quote: literal punctuation — “keep”; 한글 인용문.
> Second line: 37 litres is capacity, not actual stored volume.

## Final sentinel

FINAL-PDF-ALL-CONTENT-20261015 / 끝까지 보존.
