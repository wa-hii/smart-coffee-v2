#ifndef RELAYREGISTER_H
#define RELAYREGISTER_H

#include "DynamicVariable.h"
#include "Arduino.h"

class RelayRegister
{
    private:
        dynvar::Container<int> reg_c;
        int scl;
        int sda;
        int lat;

        void writeRegister();

    public:
        RelayRegister() {}

        void init(int, int, int, int = 8, int = 8);

        void setRelayValue(int, int );

        void setRelayValueBit(int);

        void updateRelay(){writeRegister();}

};

#endif