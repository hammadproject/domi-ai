# Home photos

The RentCast listing data has no photos. To show distinct photos on listing cards:

1. Drop image files (jpg/webp, about 800x600) in this folder.
2. List their file names in `manifest.json`, for example `["a.jpg", "b.jpg", "c.jpg"]`.

Each listing is assigned one photo from the pool by a stable hash of its id, so a given home
always gets the same image and neighbouring listings get different ones. With an empty
manifest the cards show a map of the home's location instead.

Only use images you have the right to use. A photo from this pool is NOT a photo of the
listed home: label it as illustrative wherever it is shown.
