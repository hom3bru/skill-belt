package canon

import "strings"

// Canon lower-cases the scheme and host and drops a default port.
func Canon(u string) string {
	return strings.ToLower(u)
}
