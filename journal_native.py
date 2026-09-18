"""Native-cell preparation retained in the existing immutable delivery patches."""
from copy import deepcopy
import math
import re

CELL_FIELDS = 'userEnteredValue,userEnteredFormat,dataValidation,chipRuns,textFormatRuns,note'


def address(value):
    match = re.fullmatch(r"'([^']+)'!([A-Z]+)([1-9][0-9]*)", value)
    if not match:
        raise ValueError('Invalid single-cell patch address.')
    title, letters, row = match.groups()
    column = 0
    for letter in letters:
        column = column * 26 + ord(letter) - 64
    return title, int(row) - 1, column - 1


def entered(value):
    if isinstance(value, bool):
        return {'boolValue': value}
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError('Non-finite Journal value.')
        return {'numberValue': value}
    if isinstance(value, str):
        return {'stringValue': value} if value else {}
    raise ValueError('Unsupported Journal value type.')


def prepare_patch(patch, cell, sheet_id):
    if (cell.get('userEnteredValue', {}).get('formulaValue') or cell.get('chipRuns')
            or cell.get('textFormatRuns') or cell.get('userEnteredFormat', {}).get('textFormat', {}).get('link')):
        raise ValueError('Formula or rich cell requires explicit reconciliation.')
    value = patch['values'][0][0]
    condition = cell.get('dataValidation', {}).get('condition')
    if condition and (condition.get('type') != 'ONE_OF_LIST' or str(value) not in
                      [v.get('userEnteredValue') for v in condition.get('values', [])]):
        raise ValueError('Unsupported or unsatisfied cell validation.')
    after = deepcopy(cell)
    after.pop('userEnteredValue', None)
    if entered(value):
        after['userEnteredValue'] = entered(value)
    return {**patch, 'native': {'version': 1, 'sheet_id': sheet_id,
                              'before': deepcopy(cell), 'after': after}}


def requests_for(patches):
    requests = []
    for patch in patches:
        _, row, col = address(patch['range'])
        native = patch['native']
        if native['version'] != 1:
            raise ValueError('Unknown native patch version.')
        region = {'sheetId': native['sheet_id'], 'startRowIndex': row, 'endRowIndex': row + 1,
                  'startColumnIndex': col, 'endColumnIndex': col + 1}
        requests.append({'updateCells': {'range': region,
            'rows': [{'values': [{'userEnteredValue': entered(patch['values'][0][0])}]}],
            'fields': 'userEnteredValue'}})
        # Explicitly restore date formatting and suppress Sheets' automatic URL detection.
        # Both requests run in one atomic Sheets batch; no post-write blind repair/retry.
        requests.append({'repeatCell': {'range': region,
            'cell': {'userEnteredFormat': native['after'].get('userEnteredFormat', {})},
            'fields': 'userEnteredFormat.numberFormat,userEnteredFormat.textFormat.link'}})
    return requests
