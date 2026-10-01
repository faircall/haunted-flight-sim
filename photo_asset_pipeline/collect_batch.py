from research import *
import zipfile,io

def walters():
    save_source('walters_lantern',dict(title='Lantern with Eight Daoist Immortals',accession='49.2829',
        institution='The Walters Art Museum',credit='Acquired by William T. Walters',licence='CC0',
        rights_url='https://art.thewalters.org/object/49.2829/',object_url='https://art.thewalters.org/object/49.2829/'),
        'https://art.thewalters.org/images/art/PS1_49.2829_VwA_DD_AT18-030104-tms.jpg')
def wood():
    catalog=json.loads((ROOT/'research'/'wood.txt').read_text())['foundAssets']
    for name in ('Wood058','Wood092','WoodFloor070'):
        data=next(a for a in catalog if a['assetId']==name)
        (ROOT/'research'/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf8')
        print(name,json.dumps(data)[:1900],flush=True)
def roof():
    page='https://www.goodfreephotos.com/china/bejing/beijing-jingshan-temple.jpg.php'
    html=get(page).text;(ROOT/'research'/'jingshan.html').write_text(html,encoding='utf8')
    print('jingshan',list(dict.fromkeys(re.findall(r'[^\s<>"\x27]+beijing-jingshan-temple[^\s<>"\x27]*',html)))[:15],flush=True)
if __name__=='__main__':
    for fn in (lambda:commons("Tang's lantern.jpg",'tang_lantern'),walters,
               lambda:commons('Guanyin temple roof.jpg','guanyin_roof'),roof,wood):
        try:fn()
        except Exception as exc:print(type(exc).__name__,str(exc),flush=True)
    sheet()
