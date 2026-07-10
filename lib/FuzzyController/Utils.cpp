#include "Utils.h"

std::string* breakString(std::string str, int output_length_, int buffer_length_)
{
	const int output_length = output_length_;
	const int buffer_length = buffer_length_;
	std::string* output = new std::string[output_length];
	char* buffer = new char[buffer_length];
	int buffer_count = 0;
	int output_count = 0;

	for(int i = 0;i<str.length() && output_count<output_length;i++)
	{
		if(str[i] == ' ')
		{
			buffer[buffer_count] = '\0';
			std::string output_buffer = buffer;
			output[output_count] = output_buffer;
			delete [] buffer;
			buffer = new char[buffer_length];
			buffer_count = 0;
			output_count++;
		}
		else
		{
			buffer[buffer_count] = str[i];
			buffer_count++;
		}
	}
	
	delete [] buffer;
	
	return output;
}