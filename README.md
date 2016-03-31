tesla
=====

python api for teslas

Examples:

----

```py
import tesla

#### connect to a car
account = tesla.Account(<email>, <password>)  # will read from environment if absent:
                                              # TESLA_EMAIL and TESLA_PASSWORD
                                              # (recommended for password)
cars = account.vehicles()
car = cars[0]

#### OR

car = tesla.my_car()  # only works when environment variabls are set

#### do stuff!

print car.mobile_enabled
print car.flash_lights()
print car.honk_horn()

# standard queries (rest API wrappers):
print car.mobile_enabled
print car.charge_state
print car.climate_state
print car.drive_state
print car.gui_settings
print car.vehicle_state

# custom queries:
print car.diagnostic()
print car.locate()

# standard commands (rest API wrappers):

car.charge_port_door_open()
car.charge_standard()
car.charge_max_range()
car.set_charge_limit(80) # percent
car.charge_start()
car.charge_stop()
car.flash_lights()
car.honk_horn()
car.door_unlock()
car.door_lock()
car.set_temps(68, 68) # driver, then passenger.
                      # Passenger is optional; defaults to driver
                      # Temperatures should be in whatever units
                      # the car is set to display on the gui
                      # (car.gui_settings['gui_temperature_units'])
car.auto_conditioning_start()
car.auto_conditioning_stop()
car.sun_roof_control(state) # 'open', 'comfort', 'vent', or 'close'
                            # (100%,  80%,       15%,       0%)

# custom commands:

car.go_crazy(seconds)  # randomly run lights, horn, doors, and sun roof
car.reset_state() # turn off lights, lock doors, set to room temperature, turn off AC
```

----



