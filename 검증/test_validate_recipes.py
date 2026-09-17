import copy
import importlib.util
import os
import unittest

SCRIPT = '/mnt/data/validate_recipes.py'


def load_module():
    spec = importlib.util.spec_from_file_location('validate_recipes', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_row(uid='src:1', component_uid='src:1:component:001'):
    return {
        'schema_version': '1.0',
        'recipe': {
            'recipe_uid': uid,
            'title': 'sample',
            'description': None,
            'servings': '2 servings',
            'cooking_time': '30 min',
            'difficulty': 'easy',
            'views': 10,
            'source_url': 'https://example.com/1',
            'source': 'source',
        },
        'dish': {'name': 'dish'},
        'components': [
            {
                'component': {
                    'component_uid': component_uid,
                    'raw_name': 'onion',
                    'role': 'food',
                    'index': 1,
                    'alternative_mode': 'none',
                    'evidence': 'onion 1',
                    'quality_flags': [],
                    'group': None,
                    'quantity': '1',
                    'unit': 'piece',
                    'preparation': None,
                    'detail': None,
                    'is_required': None,
                },
                'ingredient': {
                    'name': 'onion',
                    'name_normalized': 'onion',
                },
                'alternatives': [],
            }
        ],
    }


class ValidatorTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def codes(self, report, key='errors'):
        return {item['code'] for item in report[key]}

    def test_valid_row_has_no_errors(self):
        report = self.module.validate_rows([valid_row()])
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['summary']['recipe_count'], 1)
        self.assertEqual(report['summary']['component_count'], 1)

    def test_invalid_final_fields_are_reported(self):
        row = valid_row()
        row['dish'] = None
        row['components'][0]['component']['role'] = 'foods'
        row['components'][0]['component']['alternative_mode'] = 'maybe'
        row['components'][0]['component']['quality_flags'] = ['BAD_FLAG']
        report = self.module.validate_rows([row])
        codes = self.codes(report)
        self.assertIn('DISH_NULL', codes)
        self.assertIn('INVALID_ROLE', codes)
        self.assertIn('INVALID_ALTERNATIVE_MODE', codes)
        self.assertIn('INVALID_QUALITY_FLAG', codes)

    def test_duplicate_recipe_and_component_ids_are_reported(self):
        first = valid_row()
        second = valid_row()
        report = self.module.validate_rows([first, second])
        codes = self.codes(report)
        self.assertIn('DUPLICATE_RECIPE_UID', codes)
        self.assertIn('DUPLICATE_COMPONENT_UID', codes)

    def test_duplicate_component_index_in_recipe_is_reported(self):
        row = valid_row()
        second_entry = copy.deepcopy(row['components'][0])
        second_entry['component']['component_uid'] = 'src:1:component:002'
        second_entry['component']['index'] = 1
        row['components'].append(second_entry)
        report = self.module.validate_rows([row])
        self.assertIn('DUPLICATE_COMPONENT_INDEX', self.codes(report))

    def test_alternative_required_fields_are_reported(self):
        row = valid_row()
        row['components'][0]['component']['alternative_mode'] = 'replacement'
        row['components'][0]['alternatives'] = [
            {
                'ingredient': {'name': 'shallot', 'name_normalized': 'shallot'},
                'relation': {'raw_name': '', 'evidence': ''},
            }
        ]
        report = self.module.validate_rows([row])
        self.assertIn('ALTERNATIVE_RAW_NAME_REQUIRED', self.codes(report))
        self.assertIn('ALTERNATIVE_EVIDENCE_REQUIRED', self.codes(report))


if __name__ == '__main__':
    unittest.main()
