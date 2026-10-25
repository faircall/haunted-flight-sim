"""Lake-bank settlement retains authored placement, motion and other volumes."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from g_huxin_canals_direction import default_document,profile_from_document
from g_huxin_canals_surface_settings import SurfaceFogSettings
from huxin_canals_volumes import settling_water_regions
from test_huxin_canals_volume_render import region


class SettlingWaterRegionTests(unittest.TestCase):
    def setUp(self):
        self.profile=replace(profile_from_document(default_document()),surface_fog=SurfaceFogSettings(
            enabled=True,water_mask=True,water_settle=True,water_settle_start=35.,water_settle_end=47.,
            build_end=24.,reveal_start=32.,reveal_end=58.))
        self.water=region(id='volume-water-west-basin',center=(-12.,.2,18.),density=.37)
        self.house=region(id='volume-house-410',center=(-11.,2.4,-3.))
        self.regions=(self.water,self.house)

    def test_only_water_bank_height_moves_and_authored_input_stays_unchanged(self):
        before=hash(self.regions)
        for elapsed,offset in ((41.,-.775),(47.,-1.55),(60.,-1.55)):
            water,house=settling_water_regions(self.regions,self.profile,elapsed)
            self.assertEqual(water,replace(self.water,center=(-12.,.2+offset,18.)))
            self.assertIs(house,self.house)
        self.assertEqual(hash(self.regions),before)
        self.assertEqual(self.water.center,(-12.,.2,18.))

    def test_hold_reverse_scrubbing_and_legacy_modes_are_identity(self):
        for elapsed in (24.,24.5,25.,34.9,35.):
            self.assertIs(settling_water_regions(self.regions,self.profile,elapsed),self.regions)
        settled=settling_water_regions(self.regions,self.profile,41.)
        settling_water_regions(self.regions,self.profile,47.)
        self.assertEqual(settling_water_regions(self.regions,self.profile,41.),settled)
        old=replace(self.profile,surface_fog=replace(self.profile.surface_fog,water_settle=False))
        for profile,state in ((old,'canals'),(self.profile,'ordinary'),(SimpleNamespace(),'canals')):
            self.assertIs(settling_water_regions(self.regions,profile,45.,state),self.regions)


if __name__=='__main__':unittest.main()
