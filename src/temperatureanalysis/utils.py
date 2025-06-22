ABSOLUTE_ZERO_CELSIUS = -273.15

def celsius_to_kelvin(celsius: float) -> float:
    """Convert Celsius to Kelvin."""
    return celsius - ABSOLUTE_ZERO_CELSIUS

def kelvin_to_celsius(kelvin: float) -> float:
    """Convert Kelvin to Celsius."""
    return kelvin + ABSOLUTE_ZERO_CELSIUS
