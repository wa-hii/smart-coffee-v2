#include "RelayRegister.h"

void RelayRegister::writeRegister()
{
    digitalWrite(lat,LOW);
    digitalWrite(scl,LOW);
    digitalWrite(sda,LOW);

    for(int i = 0;i<reg_c.getSize();i++)
    {
        digitalWrite(sda,reg_c.at(i));
        delay(2);
        digitalWrite(scl,HIGH);
        delay(2);
        digitalWrite(scl,LOW);
        delay(2);
    }
    digitalWrite(lat,HIGH);
}

void RelayRegister::init(int scl_, int sda_, int lat_, int reg_size_, int relay_count_)
{
    reg_c.resize(reg_size_);
    scl = scl_;
    sda = sda_;
    lat = lat_;
    pinMode(scl, OUTPUT);
    pinMode(sda, OUTPUT);
    pinMode(lat, OUTPUT);
    setRelayValueBit(0b01111111);
    writeRegister();
}

void RelayRegister::setRelayValue(int relay_, int val_)
{
    reg_c.at(relay_) = val_;
}

void RelayRegister::setRelayValueBit(int bit_)
{
    for(int i = 0;i<8;i++)
    {
        if(bit_==1) reg_c.at(i) = 1;
        else reg_c.at(i) = bit_ % 2;
        bit_/=2;
    }  
}