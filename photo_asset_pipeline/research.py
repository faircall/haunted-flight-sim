"""Download public reference metadata and unchanged originals for review."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests,json,hashlib,re
from datetime import datetime,timezone
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent
HEADERS={'User-Agent':'PhotoAssetStudy/1.0 (public-domain image research; local game art study)'}
def get(url,params=None):
    r=requests.get(url,params=params,headers=HEADERS,timeout=45);r.raise_for_status();return r
def save_source(name,data,url):
    url=url.split('?utm_')[0]
    dest=ROOT/'sources'/name;dest.mkdir(parents=True,exist_ok=True)
    data['direct_image_url']=url;data['download_date']=datetime.now(timezone.utc).isoformat()
    original=dest/('original'+Path(url.split('?')[0]).suffix.lower())
    if not original.exists():original.write_bytes(get(url).content)
    data['sha256']=hashlib.sha256(original.read_bytes()).hexdigest()
    data['original_file']=str(original.relative_to(ROOT)).replace('\\','/')
    (dest/'source.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,Image.open(original).size,flush=True)
def met(number):
    url=f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{number}'
    data=get(url).json()
    if not data.get('isPublicDomain'):raise ValueError('Image not marked public domain')
    data.update(institution='The Metropolitan Museum of Art',licence='CC0 / Public Domain',
        rights_url='https://www.metmuseum.org/about-the-met/policies-and-documents/open-access',metadata_url=url)
    save_source('met_'+str(number),data,data['primaryImage'])
def commons(title,name):
    api='https://commons.wikimedia.org/w/api.php'
    raw=get(api,dict(action='query',format='json',titles='File:'+title,prop='imageinfo',iiprop='url|extmetadata')).json()
    data=next(iter(raw['query']['pages'].values()))['imageinfo'][0]
    license=data['extmetadata'].get('LicenseShortName',{}).get('value','')
    if not any(word in license.lower() for word in ('cc0','public domain')):raise ValueError(license)
    data.update(institution='Wikimedia Commons',title=title,licence=license,object_url=data['descriptionurl'],rights_url=data['descriptionurl'])
    save_source(name,data,data['url'])
def sheet():
    files=list((ROOT/'sources').glob('*/original.*'));out=Image.new('RGB',(1000,300*((len(files)+3)//4)),(42,46,48));d=ImageDraw.Draw(out)
    for i,path in enumerate(files):
        im=Image.open(path).convert('RGB');im.thumbnail((245,265));x=i%4*250;y=i//4*300
        out.paste(im,(x,y+24));d.text((x+3,y+4),path.parent.name,fill='white')
    (ROOT/'review').mkdir(exist_ok=True);out.save(ROOT/'review'/'sources.jpg')
if __name__=='__main__':
    jobs=[(met,(49519,)),(commons,('Guanyin temple roof.jpg','guanyin_roof')),
          (commons,('Water Lily.jpg','water_lily')),(commons,('Manchu Forbidden City Roof Tile Ends.jpg','manchu_roof'))]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(fn,*args) for fn,args in jobs]
        for f in futures:
            try:f.result()
            except Exception as exc:print(type(exc).__name__,str(exc),flush=True)
    sheet()
