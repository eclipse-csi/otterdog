# Merges an array of objects based on a specified key and converts the result back to an array.
local mergeByKey(arr, key) = std.objectValues(std.foldl(function(x, y) x + { [y[key]]+: y }, arr, {}));

{
  mergeByKey:: mergeByKey
}
