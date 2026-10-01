from collect_more import *
if __name__=='__main__':
    for name,slug in [('pavilion','beijing-pavilion-building'),('temple_pavilion','china-beijing-temple-and-pavilion'),('temple_door','china-beijing-doorway-at-temple')]:
        try:photo(name,'https://www.goodfreephotos.com/china/bejing/'+slug+'.jpg.php',r'/albums/.*'+slug+r'.jpg$',slug,'GoodFreePhotos')
        except Exception as e:print(e)
    sheet()
    files=list((ROOT/'sources').glob('Wood*/*Color.jpg'))
    out=Image.new('RGB',(900,300))
    for i,fn in enumerate(files):
        im=Image.open(fn).resize((300,300));out.paste(im,(i*300,0))
        ImageDraw.Draw(out).text((i*300+8,8),fn.parent.name,fill='white',stroke_width=1,stroke_fill='black')
    out.save(ROOT/'review'/'timber.jpg')
