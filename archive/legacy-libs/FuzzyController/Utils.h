#ifndef UTILS_H
#define UTILS_H

#include <string>

/**
 * @brief Function to break string into array of string. Delimiter using space (" ").
 * @param std::string, String to break.
 * @param int, Maximum array length. Any left-over string omitted. Default : 8.
 * @param int, Maximum char buffer. Limit char count per string/word. Default : 20.
**/
std::string* breakString(std::string, int=8, int=20);

#endif