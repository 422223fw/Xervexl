import math
import unittest
import hitboxes as hb


class LocomotionTests(unittest.TestCase):
    def test_supported_feet_stay_at_ground_height(self):
        for leg in (-1,1):
            for i in range(1001):
                gait=math.tau*i/1000
                stride,lift=hb.foot_step(gait,1,leg)
                self.assertLess(abs(stride),.31)
                self.assertGreaterEqual(lift,0)
                self.assertLessEqual(lift,.130001)
                if (gait/math.tau+(.5 if leg<0 else 0))%1<.60:self.assertEqual(lift,0)

    def test_feet_land_and_lift_without_position_or_velocity_jumps(self):
        epsilon=1e-5
        for phase in (0,.60,1):
            a,b,c=(hb.foot_step((phase+dt)*math.tau,1,1) for dt in (-epsilon,0,epsilon))
            for index in (0,1):
                self.assertLess(abs(a[index]-c[index]),.0001)
                self.assertAlmostEqual((b[index]-a[index])/epsilon,(c[index]-b[index])/epsilon,places=2)

    def test_idle_feet_do_not_slide_when_gait_stops_mid_step(self):
        for gait in (0,1,2,3,4,5,6):
            for leg in (-1,1):self.assertEqual(hb.foot_step(gait,0,leg),(0,0))

    def test_free_hand_swing_affects_the_actual_arm_capsule(self):
        f=dict(x=0,z=0,yaw=0,body_yaw=0,weapon='knife',block=False,move_x=0,move_z=4.4)
        f['gait']=math.pi*.5;one=hb.body_shapes(f,0)[0][5][3]
        f['gait']=math.pi*1.5;two=hb.body_shapes(f,0)[0][5][3]
        self.assertGreater(one[2]-two[2],.15)
        f.update(block=True,guard_dir='right');before=hb.free_hand_offset(f)
        f['gait']=.2;self.assertEqual(before,hb.free_hand_offset(f))

    def test_guard_blend_has_zero_endpoint_acceleration(self):
        h=.0001
        for edge in (0,1):
            self.assertLess(abs(hb.smooth(edge+h)+hb.smooth(edge-h)-2*hb.smooth(edge)),1e-10)


class RegressionTests(unittest.TestCase):
    def test_foot_step_extreme_speed(self):
        # speed >1 is clamped internally; ensure no crash
        stride, lift = hb.foot_step(math.tau, 2, 1)
        self.assertIsInstance(stride, float)
        self.assertIsInstance(lift, float)

    def test_foot_step_gait_periodicity(self):
        for leg in (-1, 1):
            s0, l0 = hb.foot_step(0, 1, leg)
            s1, l1 = hb.foot_step(math.tau, 1, leg)
            self.assertEqual((s0, l0), (s1, l1))

    def test_body_shapes_with_block(self):
        f = dict(x=0, z=0, yaw=0, body_yaw=0, weapon='knife', block=True, guard_dir='right', move_x=0, move_z=4.4, gait=0)
        shapes, shield = hb.body_shapes(f, 0)
        self.assertIsInstance(shapes, list)
        self.assertIsNone(shield)


if __name__=='__main__':unittest.main()
