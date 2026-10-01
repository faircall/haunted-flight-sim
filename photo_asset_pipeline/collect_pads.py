from collect_more import *
if __name__=='__main__':
    for name,number,slug in [('pads_full',111195,'water-lily-leaves'),('pads_pond',338809,'water-lily-leaves-on-water-surface'),('white_lily',380641,'white-water-lily-and-large-leaves')]:
        try:
            photo(name,f'https://www.publicdomainpictures.net/en/view-image.php?image={number}&picture={slug}',r'/pictures/.*/velka/.*\.jpg$',slug,'Lynn Greyling')
            im=Image.open(ROOT/'sources'/name/'original.jpg');im.thumbnail((1000,1000));im.save(ROOT/'review'/(name+'-working.png'))
        except Exception as e:print(e)
    sheet()
