# This is not working code, just an example on how to implement
# the hostgroup autoloading :)

if $hostarray[0] {
  $encgroup_0 = $hostarray[0]
}
if $hostarray[1] {
  $encgroup_1 = $hostarray[1]
}
# An so on...

$hostgroup_prefix = hiera('hostgroup_prefix', 'hg_')

# All your base are belong to us.
class{ 'base': }

$encgroup_0hg = "${hostgroup_prefix}${encgroup_0}"
if is_module_path($encgroup_0hg) {
  include "$encgroup_0hg"
}
if $encgroup_1 {
  if is_module_path("${encgroup_0hg}::${encgroup_1}") {
     include "${encgroup_0hg}::${encgroup_1}"
  }
}
# And so on...
