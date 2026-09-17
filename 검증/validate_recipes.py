import argparse
import json
import sys
from pathlib import Path

SCHEMA_VERSION = '1.0'

ROLE_VALUES = {'food', 'seasoning', 'unknown'}
ALTERNATIVE_MODE_VALUES = {'none', 'replacement', 'either_or', 'unresolved'}
QUALITY_FLAG_CODES = {
    'AMBIGUOUS_INGREDIENT',
    'AMBIGUOUS_ROLE',
    'AMBIGUOUS_QUANTITY',
    'QUANTITY_CONFLICT',
    'AMBIGUOUS_ALTERNATIVE',
    'COMPOUND_ALTERNATIVE',
    'CONFLICTING_REQUIRED_STATUS',
    'EVIDENCE_NOT_FOUND',
    'POSSIBLE_DUPLICATE_COMPONENT',
}

RECIPE_REQUIRED = ('recipe_uid', 'title', 'source', 'source_url')
RECIPE_STRING_OR_NONE = ('description', 'servings', 'cooking_time', 'difficulty')
COMPONENT_REQUIRED = (
    'component_uid',
    'raw_name',
    'role',
    'index',
    'alternative_mode',
    'evidence',
    'quality_flags',
)
COMPONENT_STRING_OR_NONE = (
    'group',
    'quantity',
    'unit',
    'preparation',
    'detail',
)
ALTERNATIVE_REQUIRED = ('raw_name', 'evidence')
ALTERNATIVE_STRING_OR_NONE = ('quantity', 'unit', 'preparation', 'condition')


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _add_issue(target, line, recipe_uid, path, code, message, value=None):
    item = {
        'line': line,
        'recipe_uid': recipe_uid,
        'path': path,
        'code': code,
        'message': message,
    }
    if value is not None:
        item['value'] = value
    target.append(item)


def _validate_items(items, require_dish=True, initial_errors=None):
    errors = list(initial_errors or [])
    warnings = []

    seen_recipe_uids = set()
    seen_component_uids = set()
    dish_names = set()
    ingredient_names = {}

    recipe_count = 0
    component_count = 0
    alternative_count = 0

    for line_no, row in items:
        recipe_count += 1
        recipe_uid = None

        if not isinstance(row, dict):
            _add_issue(
                errors, line_no, None, '$', 'ROW_NOT_OBJECT',
                'JSONL row must be an object.', type(row).__name__
            )
            continue

        if row.get('schema_version') != SCHEMA_VERSION:
            _add_issue(
                errors, line_no, None, 'schema_version', 'INVALID_SCHEMA_VERSION',
                f'Expected schema_version {SCHEMA_VERSION}.', row.get('schema_version')
            )

        recipe = row.get('recipe')
        if not isinstance(recipe, dict):
            _add_issue(
                errors, line_no, None, 'recipe', 'RECIPE_NOT_OBJECT',
                'recipe must be an object.', type(recipe).__name__
            )
            continue

        recipe_uid = recipe.get('recipe_uid')

        for key in RECIPE_REQUIRED:
            if not _nonempty_string(recipe.get(key)):
                _add_issue(
                    errors, line_no, recipe_uid, f'recipe.{key}',
                    'RECIPE_REQUIRED_FIELD', f'{key} must be a non-empty string.',
                    recipe.get(key)
                )

        if _nonempty_string(recipe_uid):
            if recipe_uid in seen_recipe_uids:
                _add_issue(
                    errors, line_no, recipe_uid, 'recipe.recipe_uid',
                    'DUPLICATE_RECIPE_UID', 'recipe_uid must be globally unique.',
                    recipe_uid
                )
            else:
                seen_recipe_uids.add(recipe_uid)

        for key in RECIPE_STRING_OR_NONE:
            value = recipe.get(key)
            if value is not None and not isinstance(value, str):
                _add_issue(
                    errors, line_no, recipe_uid, f'recipe.{key}',
                    'INVALID_RECIPE_TYPE', f'{key} must be STRING or null.',
                    type(value).__name__
                )

        views = recipe.get('views')
        if views is not None:
            if not _is_int(views):
                _add_issue(
                    errors, line_no, recipe_uid, 'recipe.views',
                    'INVALID_VIEWS_TYPE', 'views must be INTEGER or null.',
                    type(views).__name__
                )
            elif views < 0:
                _add_issue(
                    errors, line_no, recipe_uid, 'recipe.views',
                    'NEGATIVE_VIEWS', 'views must not be negative.', views
                )

        dish = row.get('dish')
        if dish is None:
            if require_dish:
                _add_issue(
                    errors, line_no, recipe_uid, 'dish', 'DISH_NULL',
                    'Final dataset requires a non-null dish.'
                )
        elif not isinstance(dish, dict):
            _add_issue(
                errors, line_no, recipe_uid, 'dish', 'DISH_NOT_OBJECT',
                'dish must be an object or null.', type(dish).__name__
            )
        elif not _nonempty_string(dish.get('name')):
            _add_issue(
                errors, line_no, recipe_uid, 'dish.name', 'DISH_NAME_INVALID',
                'dish.name must be a non-empty string.', dish.get('name')
            )
        else:
            dish_names.add(dish['name'])

        components = row.get('components')
        if not isinstance(components, list):
            _add_issue(
                errors, line_no, recipe_uid, 'components', 'COMPONENTS_NOT_LIST',
                'components must be a list.', type(components).__name__
            )
            continue

        if not components:
            _add_issue(
                errors, line_no, recipe_uid, 'components', 'COMPONENTS_EMPTY',
                'Final dataset requires at least one component.'
            )

        seen_indexes = set()

        for component_pos, entry in enumerate(components, start=1):
            component_count += 1
            base_path = f'components[{component_pos - 1}]'

            if not isinstance(entry, dict):
                _add_issue(
                    errors, line_no, recipe_uid, base_path, 'COMPONENT_ENTRY_NOT_OBJECT',
                    'Each components entry must be an object.', type(entry).__name__
                )
                continue

            component = entry.get('component')
            ingredient = entry.get('ingredient')
            alternatives = entry.get('alternatives')

            if not isinstance(component, dict):
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.component',
                    'COMPONENT_NOT_OBJECT', 'component must be an object.',
                    type(component).__name__
                )
                continue

            for key in COMPONENT_REQUIRED:
                if key not in component:
                    _add_issue(
                        errors, line_no, recipe_uid, f'{base_path}.component.{key}',
                        'COMPONENT_REQUIRED_FIELD', f'Missing required component field: {key}.'
                    )

            component_uid = component.get('component_uid')
            if not _nonempty_string(component_uid):
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.component.component_uid',
                    'COMPONENT_UID_INVALID', 'component_uid must be a non-empty string.',
                    component_uid
                )
            elif component_uid in seen_component_uids:
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.component.component_uid',
                    'DUPLICATE_COMPONENT_UID', 'component_uid must be globally unique.',
                    component_uid
                )
            else:
                seen_component_uids.add(component_uid)

            raw_name = component.get('raw_name')
            if not _nonempty_string(raw_name):
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.component.raw_name',
                    'RAW_NAME_INVALID', 'raw_name must be a non-empty string.', raw_name
                )

            role = component.get('role')
            if role not in ROLE_VALUES:
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.component.role',
                    'INVALID_ROLE', f'role must be one of {sorted(ROLE_VALUES)}.', role
                )

            index = component.get('index')
            if not _is_int(index) or index < 1:
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.component.index',
                    'INVALID_COMPONENT_INDEX', 'index must be an INTEGER >= 1.', index
                )
            elif index in seen_indexes:
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.component.index',
                    'DUPLICATE_COMPONENT_INDEX',
                    'Component.index must be unique inside one Recipe.', index
                )
            else:
                seen_indexes.add(index)

            alternative_mode = component.get('alternative_mode')
            if alternative_mode not in ALTERNATIVE_MODE_VALUES:
                _add_issue(
                    errors, line_no, recipe_uid,
                    f'{base_path}.component.alternative_mode',
                    'INVALID_ALTERNATIVE_MODE',
                    f'alternative_mode must be one of {sorted(ALTERNATIVE_MODE_VALUES)}.',
                    alternative_mode
                )

            evidence = component.get('evidence')
            if not _nonempty_string(evidence):
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.component.evidence',
                    'EVIDENCE_INVALID', 'evidence must be a non-empty string.', evidence
                )

            quality_flags = component.get('quality_flags')
            if not isinstance(quality_flags, list):
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.component.quality_flags',
                    'QUALITY_FLAGS_NOT_LIST', 'quality_flags must be LIST<STRING>.',
                    type(quality_flags).__name__
                )
            else:
                for flag in quality_flags:
                    if flag not in QUALITY_FLAG_CODES:
                        _add_issue(
                            errors, line_no, recipe_uid,
                            f'{base_path}.component.quality_flags',
                            'INVALID_QUALITY_FLAG',
                            'quality_flags contains an unknown code.', flag
                        )

            for key in COMPONENT_STRING_OR_NONE:
                value = component.get(key)
                if value is not None and not isinstance(value, str):
                    _add_issue(
                        errors, line_no, recipe_uid, f'{base_path}.component.{key}',
                        'INVALID_COMPONENT_TYPE', f'{key} must be STRING or null.',
                        type(value).__name__
                    )

            is_required = component.get('is_required')
            if is_required is not None and not isinstance(is_required, bool):
                _add_issue(
                    errors, line_no, recipe_uid,
                    f'{base_path}.component.is_required',
                    'INVALID_IS_REQUIRED_TYPE', 'is_required must be BOOLEAN or null.',
                    type(is_required).__name__
                )

            base_normalized = None
            if not isinstance(ingredient, dict):
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.ingredient',
                    'INGREDIENT_NOT_OBJECT', 'ingredient must be an object.',
                    type(ingredient).__name__
                )
            else:
                name = ingredient.get('name')
                normalized = ingredient.get('name_normalized')
                if not _nonempty_string(name):
                    _add_issue(
                        errors, line_no, recipe_uid, f'{base_path}.ingredient.name',
                        'INGREDIENT_NAME_INVALID',
                        'ingredient.name must be a non-empty string.', name
                    )
                if not _nonempty_string(normalized):
                    _add_issue(
                        errors, line_no, recipe_uid,
                        f'{base_path}.ingredient.name_normalized',
                        'INGREDIENT_NORMALIZED_INVALID',
                        'ingredient.name_normalized must be a non-empty string.', normalized
                    )
                else:
                    base_normalized = normalized
                    previous_name = ingredient_names.get(normalized)
                    if previous_name is None:
                        ingredient_names[normalized] = name
                    elif previous_name != name:
                        _add_issue(
                            warnings, line_no, recipe_uid,
                            f'{base_path}.ingredient.name',
                            'INGREDIENT_NAME_INCONSISTENT',
                            'Same name_normalized is mapped to different display names.',
                            {'name_normalized': normalized, 'first': previous_name, 'current': name}
                        )

            if not isinstance(alternatives, list):
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.alternatives',
                    'ALTERNATIVES_NOT_LIST', 'alternatives must be a list.',
                    type(alternatives).__name__
                )
                continue

            if alternatives and alternative_mode == 'none':
                _add_issue(
                    errors, line_no, recipe_uid, f'{base_path}.alternatives',
                    'ALTERNATIVES_WITH_NONE_MODE',
                    'alternatives exist but alternative_mode is none.'
                )

            if not alternatives and alternative_mode in {'replacement', 'either_or'}:
                _add_issue(
                    warnings, line_no, recipe_uid, f'{base_path}.alternatives',
                    'ALTERNATIVE_MODE_WITHOUT_TARGET',
                    'alternative_mode indicates alternatives but alternatives is empty.'
                )

            for alt_pos, alternative in enumerate(alternatives, start=1):
                alternative_count += 1
                alt_path = f'{base_path}.alternatives[{alt_pos - 1}]'

                if not isinstance(alternative, dict):
                    _add_issue(
                        errors, line_no, recipe_uid, alt_path,
                        'ALTERNATIVE_NOT_OBJECT', 'alternative must be an object.',
                        type(alternative).__name__
                    )
                    continue

                alt_ingredient = alternative.get('ingredient')
                relation = alternative.get('relation')

                if not isinstance(alt_ingredient, dict):
                    _add_issue(
                        errors, line_no, recipe_uid, f'{alt_path}.ingredient',
                        'ALTERNATIVE_INGREDIENT_NOT_OBJECT',
                        'alternative.ingredient must be an object.',
                        type(alt_ingredient).__name__
                    )
                else:
                    alt_name = alt_ingredient.get('name')
                    alt_normalized = alt_ingredient.get('name_normalized')
                    if not _nonempty_string(alt_name):
                        _add_issue(
                            errors, line_no, recipe_uid, f'{alt_path}.ingredient.name',
                            'ALTERNATIVE_INGREDIENT_NAME_INVALID',
                            'alternative ingredient name must be a non-empty string.', alt_name
                        )
                    if not _nonempty_string(alt_normalized):
                        _add_issue(
                            errors, line_no, recipe_uid,
                            f'{alt_path}.ingredient.name_normalized',
                            'ALTERNATIVE_INGREDIENT_NORMALIZED_INVALID',
                            'alternative name_normalized must be a non-empty string.',
                            alt_normalized
                        )
                    elif base_normalized == alt_normalized:
                        _add_issue(
                            warnings, line_no, recipe_uid,
                            f'{alt_path}.ingredient.name_normalized',
                            'ALTERNATIVE_SAME_AS_BASE',
                            'Alternative resolves to the same Ingredient as the base Ingredient.',
                            alt_normalized
                        )

                if not isinstance(relation, dict):
                    _add_issue(
                        errors, line_no, recipe_uid, f'{alt_path}.relation',
                        'ALTERNATIVE_RELATION_NOT_OBJECT',
                        'alternative.relation must be an object.', type(relation).__name__
                    )
                else:
                    raw_alt = relation.get('raw_name')
                    alt_evidence = relation.get('evidence')
                    if not _nonempty_string(raw_alt):
                        _add_issue(
                            errors, line_no, recipe_uid, f'{alt_path}.relation.raw_name',
                            'ALTERNATIVE_RAW_NAME_REQUIRED',
                            'ALTERNATIVE.raw_name must be a non-empty string.', raw_alt
                        )
                    if not _nonempty_string(alt_evidence):
                        _add_issue(
                            errors, line_no, recipe_uid, f'{alt_path}.relation.evidence',
                            'ALTERNATIVE_EVIDENCE_REQUIRED',
                            'ALTERNATIVE.evidence must be a non-empty string.', alt_evidence
                        )
                    for key in ALTERNATIVE_STRING_OR_NONE:
                        value = relation.get(key)
                        if value is not None and not isinstance(value, str):
                            _add_issue(
                                errors, line_no, recipe_uid,
                                f'{alt_path}.relation.{key}',
                                'INVALID_ALTERNATIVE_RELATION_TYPE',
                                f'{key} must be STRING or null.', type(value).__name__
                            )

    summary = {
        'recipe_count': recipe_count,
        'component_count': component_count,
        'alternative_count': alternative_count,
        'unique_recipe_uid_count': len(seen_recipe_uids),
        'unique_component_uid_count': len(seen_component_uids),
        'unique_dish_count': len(dish_names),
        'unique_ingredient_count': len(ingredient_names),
        'error_count': len(errors),
        'warning_count': len(warnings),
    }

    return {
        'errors': errors,
        'warnings': warnings,
        'summary': summary,
    }


def validate_rows(rows, require_dish=True):
    items = [(index, row) for index, row in enumerate(rows, start=1)]
    return _validate_items(items, require_dish=require_dish)


def validate_jsonl(path, require_dish=True):
    path = Path(path)
    items = []
    parse_errors = []

    with path.open('r', encoding='utf-8') as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                _add_issue(
                    parse_errors, line_no, None, '$', 'INVALID_JSON',
                    f'Invalid JSON: {exc.msg} at column {exc.colno}.'
                )
                continue
            items.append((line_no, row))

    report = _validate_items(
        items,
        require_dish=require_dish,
        initial_errors=parse_errors,
    )
    report['summary']['json_parse_error_count'] = len(parse_errors)
    report['summary']['nonempty_line_count'] = len(items) + len(parse_errors)
    return report


def print_report(report, max_issues=30):
    summary = report['summary']

    print('=== Recipe Graph Data Quality Report ===')
    print(f"Recipes                : {summary.get('recipe_count', 0)}")
    print(f"Components             : {summary.get('component_count', 0)}")
    print(f"Alternatives           : {summary.get('alternative_count', 0)}")
    print(f"Unique recipe_uid      : {summary.get('unique_recipe_uid_count', 0)}")
    print(f"Unique component_uid   : {summary.get('unique_component_uid_count', 0)}")
    print(f"Unique dishes          : {summary.get('unique_dish_count', 0)}")
    print(f"Unique ingredients     : {summary.get('unique_ingredient_count', 0)}")
    print(f"JSON parse errors      : {summary.get('json_parse_error_count', 0)}")
    print(f"Errors                 : {summary.get('error_count', 0)}")
    print(f"Warnings               : {summary.get('warning_count', 0)}")

    for label, issues in (('ERROR', report['errors']), ('WARNING', report['warnings'])):
        if not issues:
            continue
        print()
        print(f'--- {label} details (showing up to {max_issues}) ---')
        for issue in issues[:max_issues]:
            location = f"line={issue['line']}"
            if issue.get('recipe_uid'):
                location += f" recipe_uid={issue['recipe_uid']}"
            print(
                f"[{label}] {location} code={issue['code']} "
                f"path={issue['path']} :: {issue['message']}"
            )
        if len(issues) > max_issues:
            print(f'... {len(issues) - max_issues} more {label.lower()}s omitted')

    print()
    if report['errors']:
        print('RESULT: FAIL')
    elif report['warnings']:
        print('RESULT: PASS WITH WARNINGS')
    else:
        print('RESULT: PASS')


def main():
    parser = argparse.ArgumentParser(
        description='Validate recipe knowledge-graph JSONL data.'
    )
    parser.add_argument('jsonl', help='Path to the JSONL file to validate.')
    parser.add_argument(
        '--allow-null-dish',
        action='store_true',
        help='Allow dish=null rows. Default final-dataset validation rejects them.',
    )
    parser.add_argument(
        '--max-issues',
        type=int,
        default=30,
        help='Maximum errors and warnings to print for each category.',
    )
    args = parser.parse_args()

    report = validate_jsonl(
        args.jsonl,
        require_dish=not args.allow_null_dish,
    )
    print_report(report, max_issues=args.max_issues)
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
