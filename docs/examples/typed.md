# typed

> Auto-generated documentation for [examples.typed](../../examples/typed.py) module.

- [Fhdoc](../README.md#fhdoc-index) / [Modules](../README.md#fhdoc-modules) / [examples](index.md#examples) / typed
    - [Links](#links)
    - [MyValue](#myvalue)
    - [Typed](#typed)
        - [Typed().async_method](#typedasync_method)
        - [Typed.classmethod](#typedclassmethod)
    - [func](#func)
    - [my_deco](#my_deco)

## Links

[PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/)

## MyValue

[[find in source code]](../../examples/typed.py#L12)

```python
class MyValue():
```

## Typed

[[find in source code]](../../examples/typed.py#L16)

```python
class Typed():
    def __init__(
        _value: Union[(List[Text], Text, MyValue)] = MyValue(
            {
                'key1': 'value1',
                'key2': 'value2',
                'key3': 'value3',
                'key4': 'value4',
                'key5': 'value5',
                'key6': 'value6',
            },
        ),
        _name: Text = 'default',
    ) -> Dict[(Text, MyValue)]:
```

### Typed().async_method

[[find in source code]](../../examples/typed.py#L38)

```python
async def async_method(_value: Text) -> Text:
```

### Typed.classmethod

[[find in source code]](../../examples/typed.py#L34)

```python
@classmethod
def classmethod(_my_value: MyValue, *_args: Text, **_kwargs: Any) -> None:
```

#### See also

- [MyValue](#myvalue)

## func

[[find in source code]](../../examples/typed.py#L46)

```python
@my_deco(key='value')
def func(
    _list: Tuple[(List[Text], ...)],
    _my_value_cls: Type[MyValue] = MyValue,
    **_kwargs: None,
) -> Any:
```

#### See also

- [MyValue](#myvalue)

## my_deco

[[find in source code]](../../examples/typed.py#L42)

```python
def my_deco(key):
```
