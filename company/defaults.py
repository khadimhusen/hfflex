# H F Flex exactly as its letterhead has been typed into the purchase order
# PDFs and the dispatch challan page. Used to create the first Company row
# (seed_companies) and as the last-resort letterhead when no Company row
# exists at all (a server that has not been migrated/seeded yet), so a
# document can never fail to print for want of one. The GSTIN matches
# Customer "H F FLEX PRIVATE LIMITED".
HF_FLEX = dict(
    name='H F FLEX PVT. LTD.',
    short_name='HF',
    gstin='27AADCH3462K1ZF',
    address_line1='25, Lucky Lark Textile Park, Gardi, Vita',
    address_line2='Tal- Khanapur, Dist- Sangli, Maharashtra-415311',
    phone='8552827683, 9765643576',
    email='hfflexpvtltd@gmail.com',
    website='www.hfflex.co.in',
    is_default=True,
)
