Definition of a `Custom Property` on organization level, the following properties are supported:

| Key               | Value                          | Description                                                                    | Notes                                                     |
|-------------------|--------------------------------|--------------------------------------------------------------------------------|-----------------------------------------------------------|
| _name_            | string                         | The name of the custom property                                                |                                                           |
| _value_type_      | string                         | The type of this property, see Notes about allowed values                      | `string`, `single_select`, `multi_select` or `true_false` |
| _required_        | boolean                        | If this property is required for any repository                                |                                                           |
| _default_value_   | string or list[string] or null | The default value to assign to a repository if the property is required        |                                                           |
| _description_     | string or null                 | A description of this property                                                 |                                                           |
| _allowed_values_  | list[string] or null           | The list of allowed values if either `single_select` or `multi_select` is used |                                                           |

!!! note

    Due to a limitation of the GitHub Api, it is not possible to change the `value_type` of a `Custom Property` after its creation.
    Trying to change the property will result in an error in the `plan` / `apply` operation after validation as the change can
    only be determined after the live settings have been analyzed.

## Jsonnet Function

``` jsonnet
orgs.newCustomProperty('<name>') {
  <key>: <value>
}
```

## Validation rules

- setting `value_type` must be one of `string`, `single_select`, `multi_select` or `true_false`, otherwise an error is triggered
- using a `value_type` of either `single_select` or `multi_select` requires that also `allowed_values` is set to a non-empty list
- setting `required` to `true` while `default_value` is not set, triggers an error
- setting `required` to `false` while `default_value` is set, triggers an error
- the property `allowed_values` allows a maximum of 200 elements
- if setting `allowed_values` and `default_value` is set, all defined default values must be in the list of allowed values

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      settings+: {
        ...
        custom_properties+: [
          orgs.newCustomProperty('LABEL') {
            description: "Label for a repository",
            value_type: "string",
          }
        ]
      },

      _repositories+:: [
        ...
        orgs.newRepo('.github') {
          ...
          custom_properties: {
            label: "MY-LABEL-VALUE",
          }
        }
      ]
    }
    ```
