local newInput(type, valueSelector, name, inputName = name, optional = false) = {
  name: name,
  type: type,
  optional: optional,
  preSelector: null,
  valueSelector: valueSelector,
  selector: 'input[type="%s"][name="%s"]' % [type, inputName],
  save: 'form:has(%s) button[type="submit"]' % self.selector
};

local newCheckbox(name, inputName = name, optional = false) =
  newInput('checkbox', 'checked', name, inputName, optional);

local newTextInput(name, inputName = name, optional = false) =
  newInput('text', 'value', name, inputName, optional);

local newRadioInput(name, inputName = name, optional = false) =
  newInput('radio', 'value', name, inputName, optional);

local newSelectMenuInput(name, inputName, saveInputName, preSelector = null, optional = false) = {
  name: name,
  optional: optional,
  type: 'select-menu',
  preSelector: preSelector,
  valueSelector: 'innerText',
  selector: 'span[id="%s"]' % [inputName],
  saveSelector: '.%s' % [saveInputName],
  save: 'form:has(%s) button[type="submit"]' % self.selector
};

{
  'settings/member_privileges': [
    newCheckbox('members_can_change_repo_visibility'),
    newCheckbox('members_can_delete_repositories'),
    newCheckbox('members_can_delete_issues'),
    newCheckbox('readers_can_create_discussions', optional = true),
    newCheckbox('members_can_create_teams')
  ],

  'settings/security': [
    newCheckbox('two_factor_required')
  ],

  'settings/repository-defaults': [
    newTextInput('default_branch_name')
  ],

  'settings/packages': [
    newCheckbox('packages_containers_public', 'packages[containers][public]'),
    newCheckbox('packages_containers_internal', 'packages[containers][internal]')
  ],

  'settings/discussions': [
    newCheckbox('has_discussions', 'discussions_enabled') + { 'delay_save': 'discussion_source_repository' },
    newSelectMenuInput('discussion_source_repository', 'js-selected-repository-name', 'js-repository-name', '.select-menu-button') + { 'parent': 'has_discussions' }
  ],

  'settings/projects': [
    newCheckbox('members_can_change_project_visibility', 'organization[members_can_change_project_visibility]')
  ],

  'settings/actions': [
    newRadioInput('default_workflow_permissions', 'actions_default_workflow_permissions')
  ]
}
