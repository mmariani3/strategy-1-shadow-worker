import copy
from types import SimpleNamespace
import pytest
from journal_native import prepare_patch, requests_for
from journal_writer import GoogleSheets,JournalConflict


@pytest.mark.parametrize('text',['2026-09-18','BBAI.WS','=IMPORTXML("untrusted","x")'])
def test_literals_preserve_format_and_never_become_formulas_or_links(text):
    original={'userEnteredFormat':{'numberFormat':{'type':'DATE','pattern':'yyyy-mm-dd'},
                                  'textFormat':{'fontFamily':'Carlito','fontSize':11}}}
    saved=copy.deepcopy(original)
    patch=prepare_patch({'range':"'Scan Coverage'!A5",'values':[[text]]},original,12)
    commands=requests_for([patch])
    assert commands[0]['updateCells']['rows'][0]['values'][0]['userEnteredValue']=={'stringValue':text}
    assert commands[1]['repeatCell']['cell']['userEnteredFormat']==original['userEnteredFormat']
    assert commands[1]['repeatCell']['fields']=='userEnteredFormat.numberFormat,userEnteredFormat.textFormat.link'
    assert 'link' not in commands[1]['repeatCell']['cell']['userEnteredFormat']['textFormat']
    assert original==saved


@pytest.mark.parametrize('cell', [{'userEnteredValue':{'formulaValue':'=NOW()'}},{'chipRuns':[{'chip':{}}]},
    {'textFormatRuns':[{'startIndex':0}]},{'userEnteredFormat':{'textFormat':{'link':{'uri':'https://example.com'}}}},
    {'dataValidation':{'condition':{'type':'ONE_OF_LIST','values':[{'userEnteredValue':'Complete'}]}}}])
def test_protected_native_content_and_invalid_dropdowns_refused(cell):
    with pytest.raises(ValueError):prepare_patch({'range':"'Scan Coverage'!A5",'values':[['Partial']]},cell,12)


def test_native_read_expands_only_bounded_blank_cells_and_write_is_atomic():
    sheets=GoogleSheets.__new__(GoogleSheets);sheets.base='https://sheets.invalid'
    calls=[]
    data={'sheets':[{'properties':{'title':'Scan Coverage','sheetId':12,'gridProperties':{'rowCount':1000,'columnCount':26}},
                    'data':[{'startRow':4,'rowData':[{'values':[{'userEnteredFormat':{'numberFormat':{'type':'DATE','pattern':'yyyy-mm-dd'}}}]}]}]}]}
    def get(url,**kwargs):
        calls.append(kwargs)
        assert kwargs['params']['fields'].count('(')==kwargs['params']['fields'].count(')')
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:data)
    def post(url,**kwargs):calls.append((url,kwargs));return SimpleNamespace(raise_for_status=lambda:None)
    sheets.http=SimpleNamespace(get=get,post=post)
    patches=sheets.prepare([{'range':"'Scan Coverage'!R5",'values':[['run']]}])
    assert patches[0]['native']['before']=={}
    sheets.verify_native(patches,'before')
    sheets.write(patches)
    assert calls[-1][0].endswith(':batchUpdate')
    assert len(calls[-1][1]['json']['requests'])==2
    with pytest.raises(JournalConflict):sheets.verify_native(patches,'after')
