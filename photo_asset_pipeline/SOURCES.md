# Source and rights ledger

All selected photos below had an **image-specific CC0/public-domain statement**
when checked for this batch on 1 October 2026 (Australia/Sydney). Source pages and
metadata are preserved under `research/` and `sources/`. Originals are unchanged;
the build verifies their SHA-256. Credit is retained even where not required.

| Source ID | Credit and photograph | Image-specific rights / original source | Used for |
| --- | --- | --- | --- |
| temple_pavilion | GoodFreePhotos; Temple and Pavilion in Beijing, photographed 2013 | [CC0 image page](https://www.goodfreephotos.com/china/bejing/china-beijing-temple-and-pavilion.jpg.php) | Original intact upper roof and painted fascia; rectified tile, tile-end and fascia textures for the Blender roof |
| pavilion | GoodFreePhotos; Pavilion Building at Beijing, photographed 2013 | [CC0 image page](https://www.goodfreephotos.com/china/bejing/beijing-pavilion-building.jpg.php) | Worn red pillar, perspective-corrected |
| tang_lantern | Wikimedia contributor 200818307connie08; Tang's lantern, 2009 | [File page and photographer's CC0 dedication](https://commons.wikimedia.org/wiki/File:Tang%27s_lantern.jpg) | Paper lantern, old timber beam/post fragments, grey brick |
| walters_lantern | The Walters Art Museum; Lantern with Eight Daoist Immortals, accession 49.2829; acquired by William T. Walters | [Object page: each photograph's Download Image is labelled Creative Commons Zero](https://art.thewalters.org/object/49.2829/) | Whole porcelain lantern, photograph VwA |
| Wood058 | ambientCG; Wood 058, a photo texture using height-field photogrammetry | [Asset page](https://ambientcg.com/view?id=Wood058), [CC0 terms](https://docs.ambientcg.com/license/) | Floor grain, wall timber, piles |
| pads_pond | Lynn Greyling / PublicDomainPictures; Water Lily Leaves on Water Surface | [Photograph and explicit CC0 release](https://www.publicdomainpictures.net/en/view-image.php?image=338809&picture=water-lily-leaves-on-water-surface) | Two intact lily pads |
| white_lily | Lynn Greyling / PublicDomainPictures; White Water Lily and Large Leaves | [Photograph and explicit CC0 release](https://www.publicdomainpictures.net/en/view-image.php?image=380641&picture=white-water-lily-and-large-leaves) | Default white flower |
| water_lily | Dinkum / Wikimedia Commons; Water Lily, Kew Gardens, 27 April 2013 | [File page and CC0 dedication](https://commons.wikimedia.org/wiki/File:Water_Lily.jpg) | Optional purple flower |

Direct original image URLs, full download timestamps and hashes are in each
`sources/<id>/source.json`. PublicDomainPictures' free 1920-pixel images were
sufficient for these tiny sprites; no premium image was purchased. The timber
colour image was extracted unchanged from the original 2K JPEG scan archive;
its supplied normal/displacement maps are preserved for future experiments.

The Blender roof's four photographic texture crops are recorded separately in
[blender/texture_sources.json](blender/texture_sources.json), with source IDs,
crop coordinates and output hashes. Its fourth texture uses the `tang_lantern`
timber photograph. The roof geometry is authored, not a scan of either building.

## Other candidates retained for reference

| Candidate | Decision |
| --- | --- |
| Met Central Watchtower, 49519 / 1984.397a,b | Official API marks the photo public domain; green-glazed ceramic architecture has attractive wear, but perspective/material were less suitable for this roof. Original retained. [Object](https://www.metmuseum.org/art/collection/search/49519) / [open access](https://www.metmuseum.org/about-the-met/policies-and-documents/open-access). |
| Guanyin temple roof | CC0 photo, but left roof edge is clipped. Not reconstructed or used. [File](https://commons.wikimedia.org/wiki/File:Guanyin_temple_roof.jpg). |
| Jingshan Temple | CC0, building too distant / crowd foreground. Not used. [Photo](https://www.goodfreephotos.com/china/bejing/beijing-jingshan-temple.jpg.php). |
| Gateway to Lama Temple | CC0, useful red wall but roof clipped. Not used. [Photo](https://www.goodfreephotos.com/china/bejing/china-beijing-gateway-to-lama-temple.jpg.php). |
| Doorway at Temple | CC0, strong pre-existing HDR treatment undermines the intended photographic palette. Not used. [Photo](https://www.goodfreephotos.com/china/bejing/china-beijing-doorway-at-temple.jpg.php). |
| Marina Shemesh, Water Lily Leaves | CC0, large foreground leaves clipped by the image boundary. Not reconstructed. [Photo](https://www.publicdomainpictures.net/en/view-image.php?image=17221&picture=water-lily-leaves). |
| Lynn Greyling, Water Lily Leaves | CC0, overlapping or clipped major leaves. The pond source gave cleaner intact silhouettes. [Photo](https://www.publicdomainpictures.net/en/view-image.php?image=111195&picture=water-lily-leaves). |
| ambientCG Wood092 | Verified photogrammetric CC0 scan; cleaner orange timber than desired. Retained as an alternative. [Asset](https://ambientcg.com/view?id=Wood092). |
| ambientCG WoodFloor070 | Verified CC0 photographic scan, but parquet pattern does not suit the outdoor deck. Not used. [Asset](https://ambientcg.com/view?id=WoodFloor070). |

No generated image, generative reconstruction, paid download, share-alike or
attribution-required source is part of the selected asset set. Board joints and
rail geometry are explicitly authored assembly geometry; their surface detail is
photographic. Identifiable objects and inscriptions are preserved as photographed.
