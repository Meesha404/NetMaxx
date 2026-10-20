import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'app'))
import server
class IntentTests(unittest.TestCase):
 def setUp(self):
  self.s=server.sample();self.p={'profile':self.s['profile'],'attendees':self.s['attendees'],'objective':self.s['objective']}
 def run_goal(self,text,**extra):return server.rank({**self.p,'objective':text,**extra})
 def test_modes_reorder_actual_pilot(self):
  peers=self.run_goal('people with similar professional experience')
  hiring=self.run_goal('people who can hire me')
  social=self.run_goal('people to date and have fun with')
  self.assertEqual(hiring['results'][0]['Attendee Name'],'Spencer Olmos')
  self.assertEqual(social['results'][0]['Attendee Name'],'Devon Sun')
  self.assertNotEqual(peers['results'][0]['Attendee Name'],hiring['results'][0]['Attendee Name'])
  self.assertEqual(len(social['top_candidate_urls']),2)
 def test_social_not_reordered_by_professional_achievements(self):
  a=self.run_goal('friendship');b=self.run_goal('friendship',profile='CEO billionaire founder PhD executive')
  self.assertEqual(a['top_candidate_urls'],b['top_candidate_urls'])
 def test_gender_returns_no_confirmed_matches(self):
  r=self.run_goal('female people')
  self.assertEqual(r['top_candidate_urls'],[])
  self.assertTrue(all(x['score'] is None for x in r['results']))
 def test_jazz_and_humor_differ(self):
  a=self.run_goal('friendship',interests='jazz');b=self.run_goal('friendship',interests='humor')
  self.assertEqual(a['results'][0]['Attendee Name'],'Devon Sun')
  self.assertEqual(b['results'][0]['Attendee Name'],'Grant Reaber')
 def test_negated_dating_and_mixed_intent(self):
  self.assertEqual(self.run_goal('professional connections, not dating')['mode'],'peers')
  with self.assertRaises(ValueError):self.run_goal('hiring and dating')
 def test_unknown_request_needs_clarification(self):
  with self.assertRaises(ValueError):self.run_goal('purple pineapple')
 def test_founder_not_claimed_actively_hiring(self):
  r=self.run_goal('hire me');founder=next(x for x in r['results'] if x['Attendee Name']=='Grant Reaber')
  self.assertIn('unconfirmed',founder['status'])
 def test_unknown_identity_and_changed_company_withheld(self):
  people=[{'Attendee Name':'Unknown','LinkedIn URL':'https://linkedin.com/in/unknown'}]
  self.assertEqual(self.run_goal('social',attendees=people)['top_candidate_urls'],[])
  people=copy.deepcopy(self.s['attendees']);people[-1]['Current Company']='Different'
  r=self.run_goal('social',attendees=people)
  self.assertFalse(next(x for x in r['results'] if x['Attendee Name']=='Devon Sun')['eligible'])
if __name__=='__main__':unittest.main()
