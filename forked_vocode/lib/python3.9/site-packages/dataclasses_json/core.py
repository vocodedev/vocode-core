import copy
import json
import warnings
from collections import defaultdict, namedtuple
from dataclasses import (MISSING,
                         fields,
                         is_dataclass  # type: ignore
                         )
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import (Any, Collection, Mapping, Union, get_type_hints,
                    Tuple, TypeVar)
from uuid import UUID

from typing_inspect import is_union_type  # type: ignore

from dataclasses_json import cfg
from dataclasses_json.utils import (_get_type_cons, _get_type_origin,
                                    _handle_undefined_parameters_safe,
                                    _is_collection, _is_mapping, _is_new_type,
                                    _is_optional, _isinstance_safe,
                                    _get_type_arg_param,
                                    _get_type_args,
                                    _NO_ARGS,
                                    _issubclass_safe, _is_tuple)

Json = Union[dict, list, str, int, float, bool, None]

confs = ['encoder', 'decoder', 'mm_field', 'letter_case', 'exclude']
FieldOverride = namedtuple('FieldOverride', confs)  # type: ignore


class _ExtendedEncoder(json.JSONEncoder):
    def default(self, o) -> Json:
        result: Json
        if _isinstance_safe(o, Collection):
            if _isinstance_safe(o, Mapping):
                result = dict(o)
            else:
                result = list(o)
        elif _isinstance_safe(o, datetime):
            result = o.timestamp()
        elif _isinstance_safe(o, UUID):
            result = str(o)
        elif _isinstance_safe(o, Enum):
            result = o.value
        elif _isinstance_safe(o, Decimal):
            result = str(o)
        else:
            result = json.JSONEncoder.default(self, o)
        return result


def _user_overrides_or_exts(cls):
    global_metadata = defaultdict(dict)
    encoders = cfg.global_config.encoders
    decoders = cfg.global_config.decoders
    mm_fields = cfg.global_config.mm_fields
    for field in fields(cls):
        if field.type in encoders:
            global_metadata[field.name]['encoder'] = encoders[field.type]
        if field.type in decoders:
            global_metadata[field.name]['decoder'] = decoders[field.type]
        if field.type in mm_fields:
            global_metadata[field.name]['mm_field'] = mm_fields[field.type]
    try:
        cls_config = (cls.dataclass_json_config
                      if cls.dataclass_json_config is not None else {})
    except AttributeError:
        cls_config = {}

    overrides = {}
    for field in fields(cls):
        field_config = {}
        # first apply global overrides or extensions
        field_metadata = global_metadata[field.name]
        if 'encoder' in field_metadata:
            field_config['encoder'] = field_metadata['encoder']
        if 'decoder' in field_metadata:
            field_config['decoder'] = field_metadata['decoder']
        if 'mm_field' in field_metadata:
            field_config['mm_field'] = field_metadata['mm_field']
        # then apply class-level overrides or extensions
        field_config.update(cls_config)
        # last apply field-level overrides or extensions
        field_config.update(field.metadata.get('dataclasses_json', {}))
        overrides[field.name] = FieldOverride(*map(field_config.get, confs))
    return overrides


def _encode_json_type(value, default=_ExtendedEncoder().default):
    if isinstance(value, Json.__args__):  # type: ignore
        if isinstance(value, list):
            return [_encode_json_type(i) for i in value]
        elif isinstance(value, dict):
            return {k: _encode_json_type(v) for k, v in value.items()}
        else:
            return value
    return default(value)


def _encode_overrides(kvs, overrides, encode_json=False):
    override_kvs = {}
    for k, v in kvs.items():
        if k in overrides:
            exclude = overrides[k].exclude
            # If the exclude predicate returns true, the key should be
            #  excluded from encoding, so skip the rest of the loop
            if exclude and exclude(v):
                continue
            letter_case = overrides[k].letter_case
            original_key = k
            k = letter_case(k) if letter_case is not None else k
            if k in override_kvs:
                raise ValueError(
                    f"Multiple fields map to the same JSON "
                    f"key after letter case encoding: {k}"
                )

            encoder = overrides[original_key].encoder
            v = encoder(v) if encoder is not None else v

        if encode_json:
            v = _encode_json_type(v)
        override_kvs[k] = v
    return override_kvs


def _decode_letter_case_overrides(field_names, overrides):
    """Override letter case of field names for encode/decode"""
    names = {}
    for field_name in field_names:
        field_override = overrides.get(field_name)
        if field_override is not None:
            letter_case = field_override.letter_case
            if letter_case is not None:
                names[letter_case(field_name)] = field_name
    return names


def _decode_dataclass(cls, kvs, infer_missing):
    if _isinstance_safe(kvs, cls):
        return kvs
    overrides = _user_overrides_or_exts(cls)
    kvs = {} if kvs is None and infer_missing else kvs
    field_names = [field.name for field in fields(cls)]
    decode_names = _decode_letter_case_overrides(field_names, overrides)
    kvs = {decode_names.get(k, k): v for k, v in kvs.items()}
    missing_fields = {field for field in fields(cls) if field.name not in kvs}

    for field in missing_fields:
        if field.default is not MISSING:
            kvs[field.name] = field.default
        elif field.default_factory is not MISSING:
            kvs[field.name] = field.default_factory()
        elif infer_missing:
            kvs[field.name] = None

    # Perform undefined parameter action
    kvs = _handle_undefined_parameters_safe(cls, kvs, usage="from")

    init_kwargs = {}
    types = get_type_hints(cls)
    for field in fields(cls):
        # The field should be skipped from being added
        # to init_kwargs as it's not intended as a constructor argument.
        if not field.init:
            continue

        field_value = kvs[field.name]
        field_type = types[field.name]
        if field_value is None:
            if not _is_optional(field_type):
                warning = (
                    f"value of non-optional type {field.name} detected "
                    f"when decoding {cls.__name__}"
                )
                if infer_missing:
                    warnings.warn(
                        f"Missing {warning} and was defaulted to None by "
                        f"infer_missing=True. "
                        f"Set infer_missing=False (the default) to prevent "
                        f"this behavior.", RuntimeWarning
                    )
                else:
                    warnings.warn(
                        f"'NoneType' object {warning}.", RuntimeWarning
                    )
            init_kwargs[field.name] = field_value
            continue

        while True:
            if not _is_new_type(field_type):
                break

            field_type = field_type.__supertype__

        if (field.name in overrides
                and overrides[field.name].decoder is not None):
            # FIXME hack
            if field_type is type(field_value):
                init_kwargs[field.name] = field_value
            else:
                init_kwargs[field.name] = overrides[field.name].decoder(
                    field_value)
        elif is_dataclass(field_type):
            # FIXME this is a band-aid to deal with the value already being
            # serialized when handling nested marshmallow schema
            # proper fix is to investigate the marshmallow schema generation
            # code
            if is_dataclass(field_value):
                value = field_value
            else:
                value = _decode_dataclass(field_type, field_value,
                                          infer_missing)
            init_kwargs[field.name] = value
        elif _is_supported_generic(field_type) and field_type != str:
            init_kwargs[field.name] = _decode_generic(field_type,
                                                      field_value,
                                                      infer_missing)
        else:
            init_kwargs[field.name] = _support_extended_types(field_type,
                                                              field_value)

    return cls(**init_kwargs)


def _support_extended_types(field_type, field_value):
    if _issubclass_safe(field_type, datetime):
        # FIXME this is a hack to deal with mm already decoding
        # the issue is we want to leverage mm fields' missing argument
        # but need this for the object creation hook
        if isinstance(field_value, datetime):
            res = field_value
        else:
            tz = datetime.now(timezone.utc).astimezone().tzinfo
            res = datetime.fromtimestamp(field_value, tz=tz)
    elif _issubclass_safe(field_type, Decimal):
        res = (field_value
               if isinstance(field_value, Decimal)
               else Decimal(field_value))
    elif _issubclass_safe(field_type, UUID):
        res = (field_value
               if isinstance(field_value, UUID)
               else UUID(field_value))
    elif _issubclass_safe(field_type, (int, float, str, bool)):
        res = (field_value
               if isinstance(field_value, field_type)
               else field_type(field_value))
    else:
        res = field_value
    return res


def _is_supported_generic(type_):
    if type_ is _NO_ARGS:
        return False
    not_str = not _issubclass_safe(type_, str)
    is_enum = _issubclass_safe(type_, Enum)
    return (not_str and _is_collection(type_)) or _is_optional(
        type_) or is_union_type(type_) or is_enum


def _decode_generic(type_, value, infer_missing):
    if value is None:
        res = value
    elif _issubclass_safe(type_, Enum):
        # Convert to an Enum using the type as a constructor.
        # Assumes a direct match is found.
        res = type_(value)
    # FIXME this is a hack to fix a deeper underlying issue. A refactor is due.
    elif _is_collection(type_):
        if _is_mapping(type_):
            k_type, v_type = _get_type_args(type_, (Any, Any))
            # a mapping type has `.keys()` and `.values()`
            # (see collections.abc)
            ks = _decode_dict_keys(k_type, value.keys(), infer_missing)
            vs = _decode_items(v_type, value.values(), infer_missing)
            xs = zip(ks, vs)
        elif _is_tuple(type_):
            types = _get_type_args(type_)
            if Ellipsis in types:
                xs = _decode_items(types[0], value, infer_missing)
            else:
                xs = _decode_items(_get_type_args(type_) or _NO_ARGS, value, infer_missing)
        else:
            xs = _decode_items(_get_type_arg_param(type_, 0), value, infer_missing)

        # get the constructor if using corresponding generic type in `typing`
        # otherwise fallback on constructing using type_ itself
        materialize_type = type_
        try:
            materialize_type = _get_type_cons(type_)
        except (TypeError, AttributeError):
            pass
        res = materialize_type(xs)
    else:  # Optional or Union
        _args = _get_type_args(type_)
        if _args is _NO_ARGS:
            # Any, just accept
            res = value
        elif _is_optional(type_) and len(_args) == 2:  # Optional
            type_arg = _get_type_arg_param(type_, 0)
            if is_dataclass(type_arg) or is_dataclass(value):
                res = _decode_dataclass(type_arg, value, infer_missing)
            elif _is_supported_generic(type_arg):
                res = _decode_generic(type_arg, value, infer_missing)
            else:
                res = _support_extended_types(type_arg, value)
        else:  # Union (already decoded or unsupported 'from_json' used)
            res = value
    return res


def _decode_dict_keys(key_type, xs, infer_missing):
    """
    Because JSON object keys must be strs, we need the extra step of decoding
    them back into the user's chosen python type
    """
    decode_function = key_type
    # handle NoneType keys... it's weird to type a Dict as NoneType keys
    # but it's valid...
    # Issue #341 and PR #346:
    #   This is a special case for Python 3.7 and Python 3.8.
    #   By some reason, "unbound" dicts are counted
    #   as having key type parameter to be TypeVar('KT')
    if key_type is None or key_type == Any or isinstance(key_type, TypeVar):
        decode_function = key_type = (lambda x: x)
    # handle a nested python dict that has tuples for keys. E.g. for
    # Dict[Tuple[int], int], key_type will be typing.Tuple[int], but
    # decode_function should be tuple, so map() doesn't break.
    #
    # Note: _get_type_origin() will return typing.Tuple for python
    # 3.6 and tuple for 3.7 and higher.
    elif _get_type_origin(key_type) in {tuple, Tuple}:
        decode_function = tuple
        key_type = key_type

    return map(decode_function, _decode_items(key_type, xs, infer_missing))


def _decode_items(type_args, xs, infer_missing):
    """
    This is a tricky situation where we need to check both the annotated
    type info (which is usually a type from `typing`) and check the
    value's type directly using `type()`.

    If the type_arg is a generic we can use the annotated type, but if the
    type_arg is a typevar we need to extract the reified type information
    hence the check of `is_dataclass(vs)`
    """
    def _decode_item(type_arg, x):
        if is_dataclass(type_arg) or is_dataclass(xs):
            return _decode_dataclass(type_arg, x, infer_missing)
        if _is_supported_generic(type_arg):
            return _decode_generic(type_arg, x, infer_missing)
        return x

    if _isinstance_safe(type_args, Collection) and not _issubclass_safe(type_args, Enum):
        return list(_decode_item(type_arg, x) for type_arg, x in zip(type_args, xs))
    return list(_decode_item(type_args, x) for x in xs)


def _asdict(obj, encode_json=False):
    """
    A re-implementation of `asdict` (based on the original in the `dataclasses`
    source) to support arbitrary Collection and Mapping types.
    """
    if is_dataclass(obj):
        result = []
        overrides = _user_overrides_or_exts(obj)
        for field in fields(obj):
            if overrides[field.name].encoder:
                value = getattr(obj, field.name)
            else:
                value = _asdict(
                    getattr(obj, field.name),
                    encode_json=encode_json
                )
            result.append((field.name, value))

        result = _handle_undefined_parameters_safe(cls=obj, kvs=dict(result),
                                                   usage="to")
        return _encode_overrides(dict(result), _user_overrides_or_exts(obj),
                                 encode_json=encode_json)
    elif isinstance(obj, Mapping):
        return dict((_asdict(k, encode_json=encode_json),
                     _asdict(v, encode_json=encode_json)) for k, v in
                    obj.items())
    # enum.IntFlag and enum.Flag are regarded as collections in Python 3.11, thus a check against Enum is needed
    elif isinstance(obj, Collection) and not isinstance(obj, (str, bytes, Enum)):
        return list(_asdict(v, encode_json=encode_json) for v in obj)
    else:
        return copy.deepcopy(obj)
