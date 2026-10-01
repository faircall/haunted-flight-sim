from research import *
import zipfile,io

def photo(name,page,pattern,title,credit):
    html=get(page).text
    (ROOT/'research'/(name+'.html')).write_text(html,encoding='utf8')
    urls=re.findall(r'(?:src|href)=["\x27]([^"\x27]+)["\x27]',html)
    url=next(u for u in urls if re.search(pattern,u))
    from urllib.parse import urljoin
    save_source(name,dict(title=title,credit=credit,licence='CC0',rights_url=page,object_url=page),urljoin(page,url))

def wood(name):
    data=json.loads((ROOT/'research'/(name+'.json')).read_text())
    dl=data['downloadFolders']['default']['downloadFiletypeCategories']['zip']['downloads']
    entry=next(d for d in dl if d['fileName']==name+'_2K-JPG.zip')
    dest=ROOT/'sources'/name;dest.mkdir(parents=True,exist_ok=True)
    archive=dest/entry['fileName']
    if not archive.exists():archive.write_bytes(get(entry['downloadLink']).content)
    with zipfile.ZipFile(archive) as z:
        for fn in z.namelist():
            if fn.endswith(('_Color.jpg','_NormalGL.jpg','_Displacement.jpg')):
                (dest/Path(fn).name).write_bytes(z.read(fn))
    color=dest/(name+'_2K-JPG_Color.jpg')
    data.update(licence='CC0',rights_url='https://docs.ambientcg.com/license/',
        object_url='https://ambientcg.com/view?id='+name,credit='ambientCG',
        download_date=datetime.now(timezone.utc).isoformat(),direct_image_url=entry['downloadLink'],
        original_file=str(color.relative_to(ROOT)).replace('\\','/'),sha256=hashlib.sha256(color.read_bytes()).hexdigest(),
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    (dest/'source.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    print(name,Image.open(color).size,flush=True)

if __name__=='__main__':
    jobs=[lambda:photo('jingshan','https://www.goodfreephotos.com/china/bejing/beijing-jingshan-temple.jpg.php',
        r'/albums/.*beijing-jingshan-temple.jpg$', 'Jingshan Temple, Beijing', 'GoodFreePhotos'),
        lambda:photo('lama_gate','https://www.goodfreephotos.com/china/bejing/china-beijing-gateway-to-lama-temple.jpg.php',
        r'/albums/.*china-beijing-gateway-to-lama-temple.jpg$', 'Gateway to Lama Temple, Beijing','GoodFreePhotos'),
        lambda:photo('lily_pads','https://www.publicdomainpictures.net/en/view-image.php?image=17221&picture=water-lily-leaves',
        r'/pictures/.*water-lily-leaves.*\.jpg$', 'Water Lily Leaves','Marina Shemesh'),
        lambda:wood('Wood058'),lambda:wood('Wood092'),lambda:wood('WoodFloor070')]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for f in [pool.submit(fn) for fn in jobs]:
            try:f.result()
            except Exception as e:print(type(e).__name__,str(e),flush=True)
    sheet()
