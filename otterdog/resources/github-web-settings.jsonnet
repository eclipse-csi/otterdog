local newInput(type, valueSelector, name, inputName = name) = {
  name: name,
  type: type,
  preSelector: null,
  valueSelector: valueSelector,
  selector: 'input[type="%s"][name="%s"]' % [type, inputName],
  save: 'form:has(%s) button[type="submit"]' % self.selector
};

local newCheckbox(name, inputName = name) =
  newInput('checkbox', 'checked', name, inputName);

local newTextInput(name, inputName = name) =
  newInput('text', 'value', name, inputName);

local newRadioInput(name, inputName = name) =
  newInput('radio', 'value', name, inputName);

local newSelectMenuInput(name, inputName, saveInputName, preSelector = null) = {
  name: name,
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
    newCheckbox('readers_can_create_discussions'),
    newCheckbox('members_can_create_teams')
  ],

  'settings/security': [
    newCheckbox('two_factor_requirement')
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