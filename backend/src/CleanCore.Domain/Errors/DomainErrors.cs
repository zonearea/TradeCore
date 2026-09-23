using CleanCore.Domain.Common;

namespace CleanCore.Domain.Errors;

public static class UserErrors
{
    public static readonly Error EmailAlreadyInUse = new(
        "User.EmailAlreadyInUse",
        "This email address is already in use.");

    public static readonly Error InvalidCredentials = new(
        "User.InvalidCredentials",
        "The provided credentials are invalid.");

    public static readonly Error NotFound = new(
        "User.NotFound",
        "The user was not found.");
}
